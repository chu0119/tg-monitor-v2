"""Mihomo配置文件生成器"""
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
from loguru import logger

from app.proxy.subscribe_parser import ProxyNode


class ConfigGenerator:
    """生成Mihomo配置文件"""

    def __init__(self, proxy_dir: str = "proxy"):
        """
        初始化配置生成器

        Args:
            proxy_dir: 代理目录路径（相对于backend目录）
        """
        self.proxy_dir = Path(proxy_dir)
        self.config_path = self.proxy_dir / "config.yaml"

    def generate_config(
        self,
        node: ProxyNode,
        proxy_port: int = 7897,
        api_port: int = 9090,
        mode: str = "global"
    ) -> Dict[str, Any]:
        """
        生成Mihomo配置

        Args:
            node: 选中的代理节点
            proxy_port: 代理端口
            api_port: API端口
            mode: 运行模式（global/rule/direct）

        Returns:
            配置字典
        """
        # 获取节点的Clash配置
        node_config = node.to_clash_config()
        node_name = node_config.get("name", "Proxy")

        config = {
            # 基础配置
            "mixed-port": proxy_port,
            "allow-lan": False,
            "bind-address": "*",
            "mode": mode,
            "log-level": "warning",
            "ipv6": False,

            # 外部控制器
            "external-controller": f"127.0.0.1:{api_port}",
            "external-ui": None,

            # 代理节点
            "proxies": [node_config],

            # 代理组
            "proxy-groups": [
                {
                    "name": "GLOBAL",
                    "type": "select",
                    "proxies": [node_name]
                }
            ],

            # 规则
            "rules": [
                "MATCH,GLOBAL"
            ]
        }

        return config

    def save_config(self, config: Dict[str, Any]) -> bool:
        """
        保存配置到文件

        Args:
            config: 配置字典

        Returns:
            是否成功
        """
        try:
            # 确保目录存在
            self.proxy_dir.mkdir(parents=True, exist_ok=True)

            # 写入YAML文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)

            logger.info(f"Mihomo配置已保存到: {self.config_path}")
            return True

        except Exception as e:
            logger.error(f"保存Mihomo配置失败: {e}")
            return False

    def generate_and_save(
        self,
        node: ProxyNode,
        proxy_port: int = 7897,
        api_port: int = 9090,
        mode: str = "global"
    ) -> bool:
        """
        生成并保存配置

        Args:
            node: 选中的代理节点
            proxy_port: 代理端口
            api_port: API端口
            mode: 运行模式

        Returns:
            是否成功
        """
        config = self.generate_config(node, proxy_port, api_port, mode)
        return self.save_config(config)

    def read_config(self) -> Optional[Dict[str, Any]]:
        """
        读取当前配置

        Returns:
            配置字典，如果文件不存在则返回None
        """
        try:
            if not self.config_path.exists():
                return None

            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)

        except Exception as e:
            logger.error(f"读取Mihomo配置失败: {e}")
            return None

    def get_current_node_name(self) -> Optional[str]:
        """
        获取当前配置中的节点名称

        Returns:
            节点名称，如果不存在则返回None
        """
        config = self.read_config()
        if not config:
            return None

        proxies = config.get("proxies", [])
        if not proxies:
            return None

        return proxies[0].get("name")
