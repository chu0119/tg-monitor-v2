"""代理节点模型"""
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, func
from app.core.database import Base


class ProxyNode(Base):
    """代理节点表（缓存解析的节点）"""

    __tablename__ = "proxy_nodes"

    id = Column(Integer, primary_key=True, index=True, comment="节点ID")
    name = Column(String(200), nullable=False, comment="节点名称")
    type = Column(String(20), nullable=False, comment="节点类型：ss/ssr/vmess/trojan/vless/hysteria2")
    server = Column(String(200), comment="服务器地址")
    port = Column(Integer, comment="端口")
    config_json = Column(Text, comment="完整节点配置JSON")
    is_selected = Column(Boolean, default=False, comment="是否选中")
    latency_ms = Column(Integer, comment="延迟（毫秒）")
    subscription_url = Column(Text, comment="订阅链接URL")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")

    def __repr__(self):
        return f"<ProxyNode(id={self.id}, name={self.name}, type={self.type})>"
