"""多格式订阅解析器"""
import base64
import json
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from urllib.parse import urlparse, parse_qs, unquote
import yaml
from loguru import logger


def safe_b64decode(data: str) -> str:
    """
    安全的Base64解码函数，处理各种Base64格式
    支持标准Base64和URL安全Base64，自动补全padding
    """
    try:
        # 移除可能的空白字符
        data = data.strip()

        # 计算需要补充的padding
        missing_padding = len(data) % 4
        if missing_padding:
            data += '=' * (4 - missing_padding)

        # 尝试URL安全的Base64解码
        try:
            decoded = base64.urlsafe_b64decode(data)
            return decoded.decode('utf-8')
        except Exception:
            pass

        # 尝试标准Base64解码
        try:
            decoded = base64.b64decode(data)
            return decoded.decode('utf-8')
        except Exception:
            pass

        # 如果都失败，尝试不带padding的解码
        try:
            decoded = base64.urlsafe_b64decode(data + '==')
            return decoded.decode('utf-8')
        except Exception:
            pass

        raise ValueError(f"无法解码Base64数据: {data[:50]}...")

    except Exception as e:
        logger.error(f"Base64解码失败: {e}")
        raise


@dataclass
class ProxyNode:
    """统一的代理节点格式"""
    name: str
    type: str  # ss/ssr/vmess/trojan/vless/hysteria2
    server: str
    port: int
    params: Dict[str, Any]  # 协议参数

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return asdict(self)

    def to_clash_config(self) -> Dict[str, Any]:
        """转换为Clash配置格式"""
        config = {
            "name": self.name,
            "type": self.type,
            "server": self.server,
            "port": self.port,
        }

        # 根据类型添加特定参数
        if self.type == "ss":
            config.update({
                "cipher": self.params.get("method", "aes-256-gcm"),
                "password": self.params.get("password", ""),
            })
        elif self.type == "ssr":
            config.update({
                "cipher": self.params.get("method", "aes-256-cfb"),
                "password": self.params.get("password", ""),
                "protocol": self.params.get("protocol", "origin"),
                "protocol-param": self.params.get("protocol_param", ""),
                "obfs": self.params.get("obfs", "plain"),
                "obfs-param": self.params.get("obfs_param", ""),
            })
        elif self.type == "vmess":
            config.update({
                "uuid": self.params.get("uuid", ""),
                "alterId": self.params.get("alterId", 0),
                "cipher": self.params.get("cipher", "auto"),
            })
            if self.params.get("network") == "ws":
                config.update({
                    "network": "ws",
                    "ws-path": self.params.get("path", "/"),
                    "ws-headers": {"Host": self.params.get("host", self.server)},
                })
            elif self.params.get("network") == "grpc":
                config.update({
                    "network": "grpc",
                    "grpc-service-name": self.params.get("service_name", ""),
                })
            if self.params.get("tls"):
                config["tls"] = True
        elif self.type == "trojan":
            config.update({
                "password": self.params.get("password", ""),
            })
            if self.params.get("sni"):
                config["sni"] = self.params.get("sni")
            if self.params.get("skip-cert-verify"):
                config["skip-cert-verify"] = True
        elif self.type == "vless":
            config.update({
                "uuid": self.params.get("uuid", ""),
                "flow": self.params.get("flow", ""),
            })
            if self.params.get("tls"):
                config["tls"] = True
            if self.params.get("sni"):
                config["servername"] = self.params.get("sni")
        elif self.type == "hysteria2":
            config.update({
                "password": self.params.get("password", ""),
            })
            if self.params.get("sni"):
                config["sni"] = self.params.get("sni")

        return config


class SubscribeParser:
    """订阅链接解析器"""

    @staticmethod
    async def parse(url: str) -> List[ProxyNode]:
        """
        解析订阅链接，返回节点列表

        Args:
            url: 订阅链接URL

        Returns:
            节点列表
        """
        try:
            # 获取订阅内容
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    content = await response.text()

            # 检测格式并解析
            content = content.strip()

            # 尝试YAML格式（Clash）
            if content.startswith("proxies:") or content.startswith("proxy-providers:"):
                try:
                    result = await SubscribeParser._parse_clash_yaml(content)
                    if result:
                        return result
                    # 如果解析失败或返回空列表，继续尝试其他格式
                except Exception as e:
                    logger.warning(f"YAML解析失败，尝试其他格式: {e}")

            # 尝试Base64解码
            try:
                decoded = safe_b64decode(content)
                # 如果解码成功，按行解析URI
                return await SubscribeParser._parse_uri_lines(decoded)
            except Exception:
                pass

            # 尝试按行解析URI（非Base64）
            lines = content.split('\n')
            if any(line.strip().startswith(('ss://', 'ssr://', 'vmess://', 'trojan://', 'vless://', 'hysteria2://')) for line in lines):
                return await SubscribeParser._parse_uri_lines(content)

            logger.warning(f"无法识别的订阅格式: {url}")
            return []

        except Exception as e:
            logger.error(f"解析订阅失败: {url}, 错误: {e}")
            raise

    @staticmethod
    async def _parse_clash_yaml(content: str) -> List[ProxyNode]:
        """解析Clash YAML格式"""
        nodes = []
        try:
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                logger.warning("YAML内容不是有效的字典格式")
                return []

            proxies = data.get("proxies", [])
            if not proxies or not isinstance(proxies, list):
                logger.warning("YAML中未找到有效的proxies列表")
                return []

            for proxy in proxies:
                try:
                    node = ProxyNode(
                        name=proxy.get("name", "Unnamed"),
                        type=proxy.get("type", ""),
                        server=proxy.get("server", ""),
                        port=proxy.get("port", 0),
                        params={k: v for k, v in proxy.items() if k not in ["name", "type", "server", "port"]}
                    )
                    nodes.append(node)
                except Exception as e:
                    logger.warning(f"解析Clash节点失败: {proxy}, 错误: {e}")

        except Exception as e:
            logger.error(f"解析Clash YAML失败: {e}")

        return nodes

    @staticmethod
    async def _parse_uri_lines(content: str) -> List[ProxyNode]:
        """解析URI格式（每行一个）"""
        nodes = []
        lines = content.strip().split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            try:
                if line.startswith('ss://'):
                    node = await SubscribeParser._parse_ss_uri(line)
                elif line.startswith('ssr://'):
                    node = await SubscribeParser._parse_ssr_uri(line)
                elif line.startswith('vmess://'):
                    node = await SubscribeParser._parse_vmess_uri(line)
                elif line.startswith('trojan://'):
                    node = await SubscribeParser._parse_trojan_uri(line)
                elif line.startswith('vless://'):
                    node = await SubscribeParser._parse_vless_uri(line)
                elif line.startswith('hysteria2://'):
                    node = await SubscribeParser._parse_hysteria2_uri(line)
                else:
                    logger.warning(f"不支持的URI格式: {line[:50]}")
                    continue

                if node:
                    nodes.append(node)

            except Exception as e:
                logger.warning(f"解析URI失败: {line[:50]}, 错误: {e}")

        return nodes

    @staticmethod
    async def _parse_ss_uri(uri: str) -> Optional[ProxyNode]:
        """解析SS URI: ss://BASE64(method:password)@server:port#name 或带SIP003 plugin参数"""
        try:
            # 提取名称
            name = ""
            if '#' in uri:
                uri, name = uri.split('#', 1)
                name = unquote(name)

            # 移除 ss:// 前缀
            uri = uri.replace('ss://', '')

            # 尝试解析格式1: BASE64(method:password)@server:port?plugin=xxx
            if '@' in uri:
                userinfo, server_part = uri.split('@', 1)

                # 检查是否有查询参数（SIP003 plugin）
                query_params = {}
                if '?' in server_part:
                    server_part, query_string = server_part.split('?', 1)
                    query_params = parse_qs(query_string)
                    # parse_qs返回列表，转换为单个值
                    query_params = {k: v[0] if len(v) == 1 else v for k, v in query_params.items()}

                # Base64解码
                try:
                    decoded = safe_b64decode(userinfo)
                    method, password = decoded.split(':', 1)
                except Exception:
                    # 尝试格式2: method:password@server:port
                    method, password = userinfo.split(':', 1)

                server, port_str = server_part.split(':', 1)

                # 安全解析端口
                try:
                    port = int(port_str)
                except ValueError:
                    logger.error(f"无效的端口号: {port_str}")
                    return None

            else:
                # 格式3: BASE64(method:password:server:port)
                decoded = safe_b64decode(uri)
                parts = decoded.split(':')
                if len(parts) >= 4:
                    method = parts[0]
                    password = parts[1]
                    server = parts[2]
                    try:
                        port = int(parts[3])
                    except ValueError:
                        logger.error(f"无效的端口号: {parts[3]}")
                        return None
                else:
                    raise ValueError(f"Invalid SS URI format: {uri}")

            # 构建参数字典
            params = {"method": method, "password": password}

            # 处理SIP003 plugin参数
            if 'plugin' in query_params:
                plugin = query_params['plugin']
                params['plugin'] = plugin

                # 解析plugin选项
                if ';' in plugin:
                    plugin_name, plugin_opts = plugin.split(';', 1)
                    params['plugin'] = plugin_name
                    # 解析plugin选项，如: obfs=http;obfs-host=www.bing.com
                    for opt in plugin_opts.split(';'):
                        if '=' in opt:
                            key, value = opt.split('=', 1)
                            params[f'plugin-{key}'] = value

            return ProxyNode(
                name=name or f"SS-{server}",
                type="ss",
                server=server,
                port=port,
                params=params
            )

        except Exception as e:
            logger.error(f"解析SS URI失败: {uri}, 错误: {e}")
            return None

    @staticmethod
    async def _parse_ssr_uri(uri: str) -> Optional[ProxyNode]:
        """解析SSR URI: ssr://BASE64(server:port:protocol:method:obfs:base64pass/?params)"""
        try:
            # 移除 ssr:// 前缀
            uri = uri.replace('ssr://', '')

            # Base64解码
            decoded = safe_b64decode(uri)

            # 提取名称
            name = ""
            if '#' in decoded:
                decoded, name = decoded.split('#', 1)
                name = unquote(name)

            # 分离参数
            if '/?' in decoded:
                main_part, params_part = decoded.split('/?', 1)
            else:
                main_part = decoded
                params_part = ""

            # 解析主要部分
            parts = main_part.split(':')
            if len(parts) < 6:
                raise ValueError(f"Invalid SSR URI format: {main_part}")

            server = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                logger.error(f"无效的端口号: {parts[1]}")
                return None
            protocol = parts[2]
            method = parts[3]
            obfs = parts[4]
            password = safe_b64decode(parts[5])

            # 解析参数
            params = {}
            if params_part:
                for param in params_part.split('&'):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        params[key] = unquote(value)

            return ProxyNode(
                name=name or f"SSR-{server}",
                type="ssr",
                server=server,
                port=port,
                params={
                    "method": method,
                    "password": password,
                    "protocol": protocol,
                    "protocol_param": params.get("protoparam", ""),
                    "obfs": obfs,
                    "obfs_param": params.get("obfsparam", ""),
                }
            )

        except Exception as e:
            logger.error(f"解析SSR URI失败: {uri}, 错误: {e}")
            return None

    @staticmethod
    async def _parse_vmess_uri(uri: str) -> Optional[ProxyNode]:
        """解析VMess URI: vmess://BASE64(json)"""
        try:
            # 移除 vmess:// 前缀
            uri = uri.replace('vmess://', '')

            # Base64解码
            decoded = safe_b64decode(uri)

            # 解析JSON
            data = json.loads(decoded)

            # 安全解析端口
            try:
                port = int(data.get("port", 443))
            except (ValueError, TypeError):
                logger.error(f"无效的端口号: {data.get('port')}")
                return None

            return ProxyNode(
                name=data.get("ps", data.get("add", "VMess")),
                type="vmess",
                server=data.get("add", ""),
                port=port,
                params={
                    "uuid": data.get("id", ""),
                    "alterId": int(data.get("aid", 0)),
                    "cipher": data.get("scy", "auto"),
                    "network": data.get("net", "tcp"),
                    "tls": data.get("tls", "") == "tls",
                    "path": data.get("path", "/"),
                    "host": data.get("host", ""),
                }
            )

        except Exception as e:
            logger.error(f"解析VMess URI失败: {uri}, 错误: {e}")
            return None

    @staticmethod
    async def _parse_trojan_uri(uri: str) -> Optional[ProxyNode]:
        """解析Trojan URI: trojan://password@server:port?sni=xxx#name"""
        try:
            # 提取名称
            name = ""
            if '#' in uri:
                uri, name = uri.split('#', 1)
                name = unquote(name)

            # 移除 trojan:// 前缀
            uri = uri.replace('trojan://', '')

            # 解析URL
            parsed = urlparse(f"trojan://{uri}")
            password = parsed.username or ""
            server = parsed.hostname or ""
            port = parsed.port or 443

            # 解析查询参数
            params = {}
            if parsed.query:
                query_params = parse_qs(parsed.query)
                for key, value in query_params.items():
                    params[key] = value[0]

            return ProxyNode(
                name=name or f"Trojan-{server}",
                type="trojan",
                server=server,
                port=port,
                params={
                    "password": password,
                    "sni": params.get("sni", server),
                    "skip-cert-verify": params.get("allowInsecure", "0") == "1",
                }
            )

        except Exception as e:
            logger.error(f"解析Trojan URI失败: {uri}, 错误: {e}")
            return None

    @staticmethod
    async def _parse_vless_uri(uri: str) -> Optional[ProxyNode]:
        """解析VLESS URI: vless://uuid@server:port?params#name"""
        try:
            # 提取名称
            name = ""
            if '#' in uri:
                uri, name = uri.split('#', 1)
                name = unquote(name)

            # 移除 vless:// 前缀
            uri = uri.replace('vless://', '')

            # 解析URL
            parsed = urlparse(f"vless://{uri}")
            uuid = parsed.username or ""
            server = parsed.hostname or ""
            port = parsed.port or 443

            # 解析查询参数
            params = {}
            if parsed.query:
                query_params = parse_qs(parsed.query)
                for key, value in query_params.items():
                    params[key] = value[0]

            return ProxyNode(
                name=name or f"VLESS-{server}",
                type="vless",
                server=server,
                port=port,
                params={
                    "uuid": uuid,
                    "flow": params.get("flow", ""),
                    "tls": params.get("security", "") == "tls",
                    "sni": params.get("sni", server),
                    "type": params.get("type", "tcp"),
                }
            )

        except Exception as e:
            logger.error(f"解析VLESS URI失败: {uri}, 错误: {e}")
            return None

    @staticmethod
    async def _parse_hysteria2_uri(uri: str) -> Optional[ProxyNode]:
        """解析Hysteria2 URI: hysteria2://auth@server:port?sni=xxx#name"""
        try:
            # 提取名称
            name = ""
            if '#' in uri:
                uri, name = uri.split('#', 1)
                name = unquote(name)

            # 移除 hysteria2:// 前缀
            uri = uri.replace('hysteria2://', '')

            # 解析URL
            parsed = urlparse(f"hysteria2://{uri}")
            password = parsed.username or ""
            server = parsed.hostname or ""
            port = parsed.port or 443

            # 解析查询参数
            params = {}
            if parsed.query:
                query_params = parse_qs(parsed.query)
                for key, value in query_params.items():
                    params[key] = value[0]

            return ProxyNode(
                name=name or f"Hysteria2-{server}",
                type="hysteria2",
                server=server,
                port=port,
                params={
                    "password": password,
                    "sni": params.get("sni", server),
                }
            )

        except Exception as e:
            logger.error(f"解析Hysteria2 URI失败: {uri}, 错误: {e}")
            return None
