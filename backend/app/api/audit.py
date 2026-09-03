"""审计日志 API - 使用统一审计服务"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.services.audit_service import list_audit_logs, get_audit_stats

router = APIRouter(prefix="/audit", tags=["审计日志"])


@router.get("")
async def list_audit_logs_api(
    operator: str = Query(None, description="操作人筛选"),
    action_type: str = Query(None, description="操作类型筛选"),
    target_type: str = Query(None, description="目标类型筛选"),
    start_date: str = Query(None, description="开始时间"),
    end_date: str = Query(None, description="结束时间"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    """获取审计日志列表"""
    return await list_audit_logs(
        db,
        operator=operator,
        action=action_type,
        target_type=target_type,
        start_time=start_date,
        end_time=end_date,
        page=page,
        page_size=page_size,
    )


@router.get("/stats")
async def get_audit_stats_api(
    start_date: str = Query(None, description="开始时间"),
    end_date: str = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db),
):
    """获取审计统计"""
    return await get_audit_stats(db, start_time=start_date, end_time=end_date)
