"""
Worker配置管理
支持多Worker部署，每个Worker管理独立的Telegram账号组
"""
import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from loguru import logger


@dataclass
class WorkerConfig:
    """Worker配置"""
    worker_id: int
    worker_type: str  # 'api' 或 'monitor'
    port: int
    account_ids: List[int]
    session_dir: str
    log_file: str


class WorkerManager:
    """Worker管理器"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__), '..', '..', 'workers', 'config.json'
        )
        self.config = self._load_config()
        try:
            self.worker_id = int(os.environ.get('WORKER_ID', '0'))
        except (ValueError, TypeError):
            logger.warning("WORKER_ID 环境变量无效，使用默认值 0")
            self.worker_id = 0
        self.worker_type = os.environ.get('WORKER_TYPE', 'api')

    def _load_config(self) -> dict:
        """加载配置文件"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"配置文件不存在: {self.config_path}，使用默认配置")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return self._get_default_config()

    def _get_default_config(self) -> dict:
        """获取默认配置"""
        return {
            "api_workers": 1,
            "monitor_workers": 1,
            "accounts_per_worker": 5,
            "worker_ports": {
                "api": [8000],
                "monitor": [8010]
            },
            "session_dir": "sessions",
            "log_dir": "logs",
            "database": {
                "pool_size": 10,
                "max_overflow": 20
            },
            "monitor": {
                "queue_maxsize": 1000,
                "batch_size": 50,
                "semaphore_limit": 10,
                "heartbeat_interval": 30,
                "startup_timeout": 5.0
            }
        }

    def get_worker_config(self, worker_id: int = None, worker_type: str = None) -> WorkerConfig:
        """获取指定Worker的配置"""
        wid = worker_id if worker_id is not None else self.worker_id
        wtype = worker_type if worker_type is not None else self.worker_type

        if wtype == 'api':
            ports = self.config.get('worker_ports', {}).get('api', [8000])
            port = ports[wid % len(ports)]
            account_ids = []
        else:
            ports = self.config.get('worker_ports', {}).get('monitor', [8010])
            port = ports[wid % len(ports)]

            # 计算该Worker负责的账号ID范围
            accounts_per = self.config.get('accounts_per_worker', 5)
            start_id = wid * accounts_per + 1
            end_id = start_id + accounts_per
            account_ids = list(range(start_id, end_id))

        session_dir = os.path.join(
            self.config.get('session_dir', 'sessions'),
            f'worker_{wid}'
        )
        log_file = os.path.join(
            self.config.get('log_dir', 'logs'),
            f'worker_{wid}_{wtype}.log'
        )

        return WorkerConfig(
            worker_id=wid,
            worker_type=wtype,
            port=port,
            account_ids=account_ids,
            session_dir=session_dir,
            log_file=log_file
        )

    def get_all_worker_configs(self, worker_type: str = None) -> List[WorkerConfig]:
        """获取所有Worker配置"""
        configs = []
        wtype = worker_type or self.worker_type

        if wtype == 'api':
            count = self.config.get('api_workers', 1)
        else:
            count = self.config.get('monitor_workers', 1)

        for i in range(count):
            configs.append(self.get_worker_config(worker_id=i, worker_type=wtype))

        return configs

    def get_database_config(self) -> dict:
        """获取数据库配置"""
        return self.config.get('database', {})

    def get_monitor_config(self) -> dict:
        """获取监控配置"""
        return self.config.get('monitor', {})


# 全局实例
worker_manager = WorkerManager()
