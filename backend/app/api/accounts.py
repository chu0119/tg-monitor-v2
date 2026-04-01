"""Telegram 账号管理 API"""
from typing import List
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update, delete, or_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.schemas.account import (
    TelegramAccountCreate,
    TelegramAccountUpdate,
    TelegramAccountResponse,
    TelegramAccountLogin,
    TelegramAccountLoginCode,
)
from app.models.account import TelegramAccount
from app.telegram.client import client_manager

router = APIRouter(prefix="/accounts", tags=["账号管理"])


@router.get("", response_model=List[TelegramAccountResponse])
async def list_accounts(db: AsyncSession = Depends(get_db)):
    """获取账号列表"""
    result = await db.execute(select(TelegramAccount))
    accounts = result.scalars().all()
    return accounts


@router.get("/{account_id}", response_model=TelegramAccountResponse)
async def get_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """获取账号详情"""
    result = await db.execute(
        select(TelegramAccount).where(TelegramAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )
    return account


@router.post("/login/request", response_model=dict)
async def request_login_code(request: TelegramAccountLogin):
    """请求登录验证码"""
    try:
        result = await client_manager.request_login_code(
            phone=request.phone,
            api_id=request.api_id,
            api_hash=request.api_hash,
            proxy=request.proxy_config
        )
        return result
    except Exception as e:
        logger.error(f"请求验证码失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login/submit", response_model=TelegramAccountResponse)
async def submit_login_code(request: TelegramAccountLoginCode):
    """提交验证码登录"""
    try:
        account = await client_manager.sign_in_with_code(
            phone=request.phone,
            code=request.code,
            api_id=request.api_id,
            api_hash=request.api_hash,
            password=request.password
        )
        return account
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"登录失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="登录失败"
        )


@router.put("/{account_id}", response_model=TelegramAccountResponse)
async def update_account(
    account_id: int,
    update_data: TelegramAccountUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新账号"""
    result = await db.execute(
        select(TelegramAccount).where(TelegramAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(account, field, value)

    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}")
async def delete_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """删除账号（级联删除相关数据）"""
    from app.models.conversation import Conversation
    from app.models.message import Message
    from app.models.alert import Alert
    from sqlalchemy import and_

    result = await db.execute(
        select(TelegramAccount).where(TelegramAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="账号不存在"
        )

    try:
        # 断开客户端
        if account_id in client_manager.clients:
            await client_manager.clients[account_id].disconnect()
            del client_manager.clients[account_id]

        # 获取该账号的所有会话ID
        conv_result = await db.execute(
            select(Conversation.id).where(Conversation.account_id == account_id)
        )
        conversation_ids = [row[0] for row in conv_result.fetchall()]

        if conversation_ids:
            # 删除顺序：notification_logs → alerts → messages → conversations
            # 注意外键依赖链：notification_logs→alerts, alerts→messages(循环),
            # messages→conversations, conversations→accounts

            # 1. 先删除 notification_logs
            from app.models.notification_log import NotificationLog
            from app.models.notification_config import NotificationConfig
            alert_ids_result = await db.execute(
                select(Alert.id).where(
                    or_(
                        Alert.conversation_id.in_(conversation_ids)
                    )
                )
            )
            alert_ids = [row[0] for row in alert_ids_result.fetchall()]
            if alert_ids:
                await db.execute(
                    delete(NotificationLog).where(NotificationLog.alert_id.in_(alert_ids))
                )

            # 2. 删除告警（通过会话ID，避免循环外键问题）
            await db.execute(
                delete(Alert).where(
                    or_(
                        Alert.conversation_id.in_(conversation_ids)
                    )
                )
            )

            # 3. 删除相关消息
            await db.execute(
                delete(Message).where(Message.conversation_id.in_(conversation_ids))
            )

            # 4. 删除会话
            await db.execute(
                delete(Conversation).where(Conversation.account_id == account_id)
            )

        # 删除账号
        await db.delete(account)
        await db.commit()

        # 删除会话文件
        if account.session_file:
            session_path = Path(account.session_file)
            if session_path.exists():
                session_path.unlink()
                logger.info(f"已删除会话文件: {account.session_file}")

            # 清理相关文件
            for suffix in ['-journal', '-wal', '-shm']:
                related_file = Path(str(session_path) + suffix)
                if related_file.exists():
                    related_file.unlink()
                    logger.info(f"已删除相关文件: {related_file}")

        return {"message": "账号已删除"}

    except Exception as e:
        await db.rollback()
        logger.error(f"删除账号失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除账号失败: {str(e)}"
        )


@router.post("/{account_id}/dialogs")
async def get_dialogs(account_id: int):
    """获取对话列表"""
    try:
        dialogs = await client_manager.get_dialogs(account_id)
        return {"dialogs": dialogs}
    except Exception as e:
        logger.error(f"获取对话列表失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="获取对话列表失败"
        )


@router.post("/{account_id}/disconnect")
async def disconnect_account(account_id: int, db: AsyncSession = Depends(get_db)):
    """断开账号连接"""
    if account_id in client_manager.clients:
        await client_manager.clients[account_id].disconnect()
        del client_manager.clients[account_id]

        # 更新数据库状态
        await db.execute(
            update(TelegramAccount)
            .where(TelegramAccount.id == account_id)
            .values(is_active=False, is_authorized=False)
        )
        await db.commit()

    return {"message": "已断开连接"}
