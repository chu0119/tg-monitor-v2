"""通知配置 API"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.schemas.notification import (
    NotificationConfigCreate,
    NotificationConfigUpdate,
    NotificationConfigResponse,
    NotificationTest,
)
from app.models.notification_config import NotificationConfig
from app.services.notification_service import notification_service

router = APIRouter(prefix="/notifications", tags=["通知配置"])


@router.get("", response_model=List[NotificationConfigResponse])
async def list_notifications(db: AsyncSession = Depends(get_db)):
    """获取通知配置列表"""
    result = await db.execute(
        select(NotificationConfig)
        .order_by(NotificationConfig.priority.desc(), NotificationConfig.id)
    )
    configs = result.scalars().all()
    return configs


@router.get("/types", response_model=List[dict])
async def list_notification_types():
    """获取支持的通知类型"""
    from app.models.notification_config import NotificationType
    return [
        {"value": "email", "label": "邮件"},
        {"value": "dingtalk", "label": "钉钉"},
        {"value": "wecom", "label": "企业微信"},
        {"value": "serverchan", "label": "Server酱"},
        {"value": "webhook", "label": "Webhook"},
        {"value": "telegram", "label": "Telegram"},
    ]


@router.get("/{config_id}", response_model=NotificationConfigResponse)
async def get_notification(config_id: int, db: AsyncSession = Depends(get_db)):
    """获取通知配置详情"""
    result = await db.execute(
        select(NotificationConfig).where(NotificationConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知配置不存在"
        )
    return config


@router.post("", response_model=NotificationConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_notification(
    config_data: NotificationConfigCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建通知配置"""
    data_dict = config_data.model_dump()

    # 处理 min_alert_level: int 转为 str
    if "min_alert_level" in data_dict and data_dict["min_alert_level"] is not None:
        level = data_dict["min_alert_level"]
        if isinstance(level, int):
            level_map = {1: "low", 2: "medium", 3: "high", 4: "critical"}
            data_dict["min_alert_level"] = level_map.get(level, str(level))

    config = NotificationConfig(**data_dict)
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.put("/{config_id}", response_model=NotificationConfigResponse)
async def update_notification(
    config_id: int,
    update_data: NotificationConfigUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新通知配置"""
    result = await db.execute(
        select(NotificationConfig).where(NotificationConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知配置不存在"
        )

    update_dict = update_data.model_dump(exclude_unset=True)

    # 处理 min_alert_level: int 转为 str (1->"low", 2->"medium", 3->"high", 4->"critical")
    if "min_alert_level" in update_dict and update_dict["min_alert_level"] is not None:
        level = update_dict["min_alert_level"]
        if isinstance(level, int):
            level_map = {1: "low", 2: "medium", 3: "high", 4: "critical"}
            update_dict["min_alert_level"] = level_map.get(level, str(level))

    for field, value in update_dict.items():
        setattr(config, field, value)

    await db.commit()
    await db.refresh(config)
    return config


@router.delete("/{config_id}")
async def delete_notification(config_id: int, db: AsyncSession = Depends(get_db)):
    """删除通知配置"""
    result = await db.execute(
        select(NotificationConfig).where(NotificationConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知配置不存在"
        )

    await db.delete(config)
    await db.commit()

    return {"message": "通知配置已删除"}


@router.post("/test")
async def test_notification(test_data: NotificationTest, db: AsyncSession = Depends(get_db)):
    """测试通知发送"""
    result = await db.execute(
        select(NotificationConfig).where(NotificationConfig.id == test_data.config_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="通知配置不存在"
        )

    success = await notification_service.test_notification(
        config,
        test_data.test_message
    )

    if success:
        return {"message": "测试通知发送成功"}
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="测试通知发送失败"
        )
