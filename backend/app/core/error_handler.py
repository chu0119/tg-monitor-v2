"""
统一错误处理模块
提供标准化的错误响应和异常处理
"""
from typing import Any, Optional
from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger


class ErrorResponse(BaseModel):
    """统一错误响应模型"""
    success: bool = False
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None


class AppException(HTTPException):
    """应用自定义异常"""
    def __init__(
        self,
        status_code: int,
        error: str,
        detail: Optional[str] = None,
        code: Optional[str] = None
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.error = error
        self.code = code


class NotFoundException(AppException):
    """资源不存在异常"""
    def __init__(self, resource: str = "资源", resource_id: Any = None):
        detail = f"{resource}不存在" if not resource_id else f"{resource} (ID: {resource_id}) 不存在"
        super().__init__(
            status_code=404,
            error="NOT_FOUND",
            detail=detail,
            code="resource_not_found"
        )


class ValidationException(AppException):
    """参数验证异常"""
    def __init__(self, detail: str):
        super().__init__(
            status_code=400,
            error="VALIDATION_ERROR",
            detail=detail,
            code="validation_error"
        )


class PermissionException(AppException):
    """权限不足异常"""
    def __init__(self, detail: str = "权限不足"):
        super().__init__(
            status_code=403,
            error="PERMISSION_DENIED",
            detail=detail,
            code="permission_denied"
        )


class DuplicateException(AppException):
    """重复资源异常"""
    def __init__(self, resource: str = "资源", detail: Optional[str] = None):
        super().__init__(
            status_code=409,
            error="DUPLICATE",
            detail=detail or f"{resource}已存在",
            code="duplicate_resource"
        )


class RateLimitException(AppException):
    """频率限制异常"""
    def __init__(self, detail: str = "请求过于频繁，请稍后再试"):
        super().__init__(
            status_code=429,
            error="RATE_LIMIT",
            detail=detail,
            code="rate_limit_exceeded"
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """应用异常处理器"""
    logger.warning(
        f"API错误: {exc.error} - {exc.detail} | "
        f"路径: {request.url.path} | 方法: {request.method}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.error,
            detail=exc.detail,
            code=exc.code
        ).model_dump()
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP异常处理器"""
    logger.warning(
        f"HTTP错误: {exc.status_code} - {exc.detail} | "
        f"路径: {request.url.path} | 方法: {request.method}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error="HTTP_ERROR",
            detail=str(exc.detail),
            code=f"http_{exc.status_code}"
        ).model_dump()
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """通用异常处理器"""
    logger.error(
        f"未处理异常: {type(exc).__name__}: {exc} | "
        f"路径: {request.url.path} | 方法: {request.method}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="INTERNAL_ERROR",
            detail="服务器内部错误，请稍后再试",
            code="internal_error"
        ).model_dump()
    )

