"""API 认证中间件"""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import os

# API Key 配置 - 通过环境变量或 .env 文件设置
# 如果未设置 API_KEY 环境变量，则不启用认证（向后兼容）
API_KEY = os.environ.get("TG_MONITOR_API_KEY", "")

# 不需要认证的路径
EXEMPT_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc"}


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API Key 认证中间件
    
    如果配置了 TG_MONITOR_API_KEY 环境变量，则所有 /api/ 开头的请求
    都需要在 Header 中携带 X-API-Key 或在 Query 中携带 api_key 参数。
    
    未配置 API_KEY 时，所有请求直接放行（向后兼容）。
    """
    
    async def dispatch(self, request: Request, call_next):
        # 如果未配置 API Key，直接放行
        if not API_KEY:
            return await call_next(request)
        
        # 豁免路径
        path = request.url.path
        if path in EXEMPT_PATHS or not path.startswith("/api/"):
            return await call_next(request)
        
        # 检查 Header 中的 API Key
        header_key = request.headers.get("X-API-Key", "")
        if header_key == API_KEY:
            return await call_next(request)
        
        # 检查 Query 参数中的 API Key
        query_key = request.query_params.get("api_key", "")
        if query_key == API_KEY:
            return await call_next(request)
        
        # 检查 Authorization Bearer token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and auth_header[7:] == API_KEY:
            return await call_next(request)
        
        # 认证失败
        raise HTTPException(
            status_code=401,
            detail="未授权：请提供有效的 API Key (X-API-Key header 或 api_key query parameter)"
        )
