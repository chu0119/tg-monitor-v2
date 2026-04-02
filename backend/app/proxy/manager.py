"""代理管理器"""
import asyncio
import subprocess
import signal
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from loguru import logger
import aiohttp

from app.proxy.subscribe_parser import SubscribeParser, ProxyNode
from app.proxy.config_generator import ConfigGenerator


class ProxyManager:
    """代理管理器 - 管理mihomo内核的启停和节点切换"""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls, *args, **kwargs):
        """单例模式：确保只有一个ProxyManager实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    async def get_instance(cls, base_dir: str = None):
        """获取单例实例"""
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = cls(base_dir)
        return cls._instance

    def __init__(self, base_dir: str = None):
        """
        初始化代理管理器

        Args:
            base_dir: 基础目录（backend目录路径），如果为None则自动检测
        """
        if self._initialized:
            return

        if base_dir is None:
            # 自动检测backend目录
            base_dir = Path(__file__).parent.parent.parent
        else:
            base_dir = Path(base_dir)

        self.base_dir = base_dir
        self.proxy_dir = base_dir / "proxy"
        self.mihomo_path = self.proxy_dir / "mihomo"
        self.config_path = self.proxy_dir / "config.yaml"
        self.pid_file = self.proxy_dir / "mihomo.pid"

        self.parser = SubscribeParser()
        self.generator = ConfigGenerator(str(self.proxy_dir))
        self._initialized = True

    async def parse_subscription(self, url: str) -> List[ProxyNode]:
        """
        解析订阅链接，返回节点列表

        Args:
            url: 订阅链接URL

        Returns:
            节点列表
        """
        return await self.parser.parse(url)

    async def select_node(self, node: ProxyNode, proxy_port: int = 7897) -> bool:
        """
        选择节点，生成配置（不自动重启mihomo）

        Args:
            node: 选中的代理节点
            proxy_port: 代理端口

        Returns:
            是否成功
        """
        try:
            # 只生成并保存配置，不重启
            if not self.generator.generate_and_save(node, proxy_port=proxy_port):
                logger.error("生成配置失败")
                return False

            logger.info(f"已选择节点: {node.name}，配置已保存")
            return True

        except Exception as e:
            logger.error(f"选择节点失败: {e}")
            return False

    async def start(self) -> Dict[str, Any]:
        """
        启动mihomo内核

        Returns:
            {success: bool, pid: int, error: str}
        """
        try:
            # 检查是否已在运行
            if await self.is_running():
                pid = await self._read_pid()
                logger.warning(f"Mihomo已在运行 (PID: {pid})")
                return {"success": True, "pid": pid, "message": "Already running"}

            # 检查配置文件
            if not self.config_path.exists():
                logger.error("配置文件不存在")
                return {"success": False, "error": "Config file not found"}

            # 检查mihomo可执行文件
            if not self.mihomo_path.exists():
                logger.error(f"Mihomo可执行文件不存在: {self.mihomo_path}")
                return {"success": False, "error": "Mihomo binary not found"}

            # 给予执行权限
            os.chmod(self.mihomo_path, 0o755)

            # 启动进程
            cmd = [str(self.mihomo_path), "-d", str(self.proxy_dir)]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.proxy_dir),
                start_new_session=True
            )

            # 等待启动并捕获输出
            await asyncio.sleep(2)

            # 检查进程是否还在运行
            if process.poll() is not None:
                _, stderr = process.communicate()
                error_msg = stderr.decode('utf-8', errors='ignore')
                logger.error(f"Mihomo启动失败: {error_msg}")
                return {"success": False, "error": error_msg}

            else:
                # 鷻加启动成功日志
                logger.info(f"Mihomo已成功启动 (PID: {process.pid})")

            # 保存PID
            await self._write_pid(process.pid)

            logger.info(f"Mihomo已启动 (PID: {process.pid})")
            return {"success": True, "pid": process.pid}

        except Exception as e:
            logger.error(f"启动Mihomo失败: {e}")
            return {"success": False, "error": str(e)}

    async def stop(self) -> Dict[str, Any]:
        """
        停止mihomo内核

        Returns:
            {success: bool, error: str}
        """
        try:
            if not await self.is_running():
                logger.info("Mihomo未运行")
                return {"success": True, "message": "Not running"}

            pid = await self._read_pid()
            if not pid:
                logger.warning("无法读取PID")
                return {"success": False, "error": "Cannot read PID"}

            # 发送SIGTERM信号
            try:
                os.kill(pid, signal.SIGTERM)
                logger.info(f"已发送SIGTERM信号到进程 {pid}")
            except ProcessLookupError:
                logger.warning(f"进程 {pid} 不存在")
                await self._remove_pid()
                return {"success": True, "message": "Process not found"}

            # 等待进程退出
            for _ in range(10):
                await asyncio.sleep(1)
                try:
                    os.kill(pid, 0)  # 检查进程是否还在
                except ProcessLookupError:
                    # 进程已退出
                    await self._remove_pid()
                    logger.info(f"Mihomo已停止 (PID: {pid})")
                    return {"success": True, "pid": pid}

            # 如果还没退出，强制杀死
            try:
                os.kill(pid, signal.SIGKILL)
                logger.warning(f"已强制杀死进程 {pid}")
            except ProcessLookupError:
                pass

            await self._remove_pid()
            return {"success": True, "pid": pid, "message": "Force killed"}

        except Exception as e:
            logger.error(f"停止Mihomo失败: {e}")
            return {"success": False, "error": str(e)}

    async def restart(self) -> Dict[str, Any]:
        """
        重启mihomo内核

        Returns:
            {success: bool, pid: int, error: str}
        """
        try:
            # 先停止
            await self.stop()

            # 等待进程完全退出
            await asyncio.sleep(2)

            # 再启动
            return await self.start()

        except Exception as e:
            logger.error(f"重启Mihomo失败: {e}")
            return {"success": False, "error": str(e)}

    async def is_running(self) -> bool:
        """
        检查mihomo是否在运行

        Returns:
            是否在运行
        """
        try:
            pid = await self._read_pid()
            if not pid:
                return False

            # 检查进程是否存在
            try:
                os.kill(pid, 0)
                return True
            except ProcessLookupError:
                # 进程不存在，清理PID文件
                await self._remove_pid()
                return False

        except Exception as e:
            logger.error(f"检查Mihomo状态失败: {e}")
            return False

    async def get_status(self) -> Dict[str, Any]:
        """
        获取代理状态

        Returns:
            {running: bool, pid: int, current_node: str, proxy_port: int}
        """
        try:
            running = await self.is_running()
            pid = await self._read_pid() if running else None
            current_node = self.generator.get_current_node_name()

            # 从配置读取端口
            config = self.generator.read_config()
            proxy_port = config.get("mixed-port", 7897) if config else 7897

            return {
                "running": running,
                "pid": pid,
                "current_node": current_node,
                "proxy_port": proxy_port,
                "config_exists": self.config_path.exists(),
            }

        except Exception as e:
            logger.error(f"获取代理状态失败: {e}")
            return {
                "running": False,
                "error": str(e)
            }

    async def test_node(self, node: ProxyNode, test_url: str = "https://www.google.com") -> int:
        """
        测试节点延迟

        Args:
            node: 要测试的节点
            test_url: 测试URL

        Returns:
            延迟毫秒数，-1表示失败
        """
        try:
            # 临时生成配置
            temp_config_path = self.proxy_dir / "temp_config.yaml"
            temp_generator = ConfigGenerator(str(self.proxy_dir))
            temp_generator.config_path = temp_config_path

            if not temp_generator.generate_and_save(node, proxy_port=7898):
                logger.error("生成临时配置失败")
                return -1

            # 临时启动mihomo（使用不同端口）
            temp_process = subprocess.Popen(
                [str(self.mihomo_path), "-f", str(temp_config_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.proxy_dir)
            )

            try:
                # 等待启动
                await asyncio.sleep(2)

                # 测试连接
                start_time = time.time()
                timeout = aiohttp.ClientTimeout(total=10)

                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.get(
                        test_url,
                        proxy="http://127.0.0.1:7898",
                        ssl=False
                    ) as response:
                        if response.status == 200:
                            latency_ms = int((time.time() - start_time) * 1000)
                            logger.info(f"节点 {node.name} 延迟: {latency_ms}ms")
                            return latency_ms
                        else:
                            logger.warning(f"节点 {node.name} 测试失败: HTTP {response.status}")
                            return -1

            except asyncio.TimeoutError:
                logger.warning(f"节点 {node.name} 测试超时")
                return -1

            except Exception as e:
                logger.error(f"节点 {node.name} 测试失败: {e}")
                return -1

            finally:
                # 停止临时进程
                temp_process.terminate()
                try:
                    temp_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    temp_process.kill()

                # 删除临时配置
                if temp_config_path.exists():
                    temp_config_path.unlink()

        except Exception as e:
            logger.error(f"测试节点失败: {e}")
            return -1

    async def _read_pid(self) -> Optional[int]:
        """读取PID文件"""
        try:
            if not self.pid_file.exists():
                return None

            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())

        except Exception as e:
            logger.error(f"读取PID失败: {e}")
            return None

    async def _write_pid(self, pid: int):
        """写入PID文件"""
        try:
            self.proxy_dir.mkdir(parents=True, exist_ok=True)
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))
        except Exception as e:
            logger.error(f"写入PID失败: {e}")

    async def _remove_pid(self):
        """删除PID文件"""
        try:
            if self.pid_file.exists():
                self.pid_file.unlink()
        except Exception as e:
            logger.error(f"删除PID文件失败: {e}")
