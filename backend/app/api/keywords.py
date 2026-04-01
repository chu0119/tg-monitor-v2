"""关键词管理 API"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.schemas.keyword import (
    KeywordGroupCreate,
    KeywordGroupUpdate,
    KeywordGroupResponse,
    KeywordCreate,
    KeywordUpdate,
    KeywordResponse,
    KeywordBatchImport,
    KeywordTestMatchRequest,
)
from app.models.keyword import KeywordGroup, Keyword
from app.models.alert import Alert

router = APIRouter(prefix="/keywords", tags=["关键词管理"])


# 兼容旧 API 路径 /api/v1/keyword-groups
@router.get("/keyword-groups")
async def list_keyword_groups_alias(db: AsyncSession = Depends(get_db)):
    """获取关键词组列表（兼容旧路径 /keyword-groups）"""
    return await list_keyword_groups_internal(db)


# 根路径 - 返回所有关键词组（兼容前端调用）
@router.get("")
async def list_keywords_root(db: AsyncSession = Depends(get_db)):
    """获取关键词组列表（根路径别名）- 返回分页格式"""
    groups = await list_keyword_groups_internal(db)
    # 计算总关键词数
    total_keywords = sum(g.get("total_keywords", 0) for g in groups)
    return {
        "total": len(groups),
        "items_count": total_keywords,
        "items": groups
    }


async def list_keyword_groups_internal(db: AsyncSession):
    """获取关键词组列表 - 内部实现"""
    # 查询所有关键词组
    result = await db.execute(
        select(KeywordGroup).order_by(KeywordGroup.priority.desc(), KeywordGroup.id)
    )
    groups = result.scalars().all()

    # 实时计算每个组的实际关键词数量并构建响应
    groups_list = []
    for group in groups:
        # 计算该组的实际关键词数量
        count_result = await db.execute(
            select(func.count(Keyword.id))
            .where(Keyword.group_id == group.id)
        )
        actual_count = count_result.scalar() or 0

        # 构建响应字典
        group_dict = {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "match_type": group.match_type,
            "case_sensitive": group.case_sensitive,
            "alert_level": group.alert_level,
            "enable_notification": group.enable_notification,
            "notification_channels": group.notification_channels,
            "is_active": group.is_active,
            "priority": group.priority,
            "total_keywords": actual_count,  # 使用实际计算的数量
            "total_matches": group.total_matches,
            "created_at": group.created_at,
            "updated_at": group.updated_at,
            "color": group.color,
        }
        groups_list.append(group_dict)

    return groups_list


# 关键词组相关
@router.get("/groups")
async def list_keyword_groups(db: AsyncSession = Depends(get_db)):
    """获取关键词组列表 - 包含实时统计的关键词数量"""
    return await list_keyword_groups_internal(db)


@router.get("/groups/{group_id}", response_model=KeywordGroupResponse)
async def get_keyword_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """获取关键词组详情"""
    result = await db.execute(
        select(KeywordGroup).where(KeywordGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="关键词组不存在"
        )
    return group


@router.post("/groups", response_model=KeywordGroupResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword_group(
    group_data: KeywordGroupCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建关键词组"""
    group = KeywordGroup(**group_data.model_dump())
    db.add(group)
    await db.commit()
    await db.refresh(group)
    return group


@router.put("/groups/{group_id}", response_model=KeywordGroupResponse)
async def update_keyword_group(
    group_id: int,
    update_data: KeywordGroupUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新关键词组"""
    result = await db.execute(
        select(KeywordGroup).where(KeywordGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="关键词组不存在"
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(group, field, value)

    await db.commit()
    await db.refresh(group)
    return group


@router.delete("/groups/{group_id}")
async def delete_keyword_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """删除关键词组"""
    result = await db.execute(
        select(KeywordGroup).where(KeywordGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="关键词组不存在"
        )

    await db.delete(group)
    await db.commit()

    return {"message": "关键词组已删除"}


# 关键词相关
@router.get("/groups/{group_id}/keywords", response_model=List[KeywordResponse])
async def list_keywords(group_id: int, db: AsyncSession = Depends(get_db)):
    """获取关键词列表"""
    result = await db.execute(
        select(Keyword)
        .where(Keyword.group_id == group_id)
        .order_by(Keyword.id)
    )
    keywords = result.scalars().all()
    return keywords


@router.post("/keywords", response_model=KeywordResponse, status_code=status.HTTP_201_CREATED)
async def create_keyword(
    keyword_data: KeywordCreate,
    db: AsyncSession = Depends(get_db),
):
    """创建关键词"""
    keyword = Keyword(**keyword_data.model_dump())
    db.add(keyword)
    await db.flush()  # 获取 keyword.id

    # 使用 SQLAlchemy update 语句更新关键词组统计，确保持久化
    await db.execute(
        update(KeywordGroup)
        .where(KeywordGroup.id == keyword.group_id)
        .values(total_keywords=KeywordGroup.total_keywords + 1)
    )

    await db.commit()
    await db.refresh(keyword)
    return keyword


@router.put("/keywords/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(
    keyword_id: int,
    update_data: KeywordUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新关键词"""
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id)
    )
    keyword = result.scalar_one_or_none()
    if not keyword:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="关键词不存在"
        )

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(keyword, field, value)

    await db.commit()
    await db.refresh(keyword)
    return keyword


@router.delete("/keywords/{keyword_id}")
async def delete_keyword(keyword_id: int, db: AsyncSession = Depends(get_db)):
    """删除关键词"""
    result = await db.execute(
        select(Keyword).where(Keyword.id == keyword_id)
    )
    keyword = result.scalar_one_or_none()
    if not keyword:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="关键词不存在"
        )

    group_id = keyword.group_id

    # 先删除引用此关键词的告警记录
    from app.models.alert import Alert
    await db.execute(
        delete(Alert).where(Alert.keyword_id == keyword_id)
    )

    # 然后删除关键词
    await db.delete(keyword)
    await db.flush()

    # 使用 SQLAlchemy update 语句更新关键词组统计，确保持久化
    await db.execute(
        update(KeywordGroup)
        .where(KeywordGroup.id == group_id)
        .values(total_keywords=KeywordGroup.total_keywords - 1)
    )

    await db.commit()

    return {"message": "关键词已删除"}


@router.post("/keywords/batch-import")
async def batch_import_keywords(
    import_data: KeywordBatchImport,
    db: AsyncSession = Depends(get_db),
):
    """批量导入关键词"""
    # 验证关键词组存在
    group_result = await db.execute(
        select(KeywordGroup).where(KeywordGroup.id == import_data.group_id)
    )
    group = group_result.scalar_one_or_none()
    if not group:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="关键词组不存在"
        )

    # 如果覆盖，删除现有关键词
    if import_data.overwrite:
        await db.execute(
            delete(Keyword).where(Keyword.group_id == import_data.group_id)
        )

    # 批量添加关键词
    created_count = 0
    for word in import_data.keywords:
        word = word.strip()
        if not word:
            continue

        # 检查是否已存在
        existing = await db.execute(
            select(Keyword).where(
                Keyword.group_id == import_data.group_id,
                Keyword.word == word
            )
        )
        if not existing.scalar_one_or_none():
            keyword = Keyword(
                group_id=import_data.group_id,
                word=word,
            )
            db.add(keyword)
            created_count += 1

    # 使用 SQLAlchemy update 语句更新关键词组统计，确保持久化
    count_result = await db.execute(
        select(func.count(Keyword.id))
        .where(Keyword.group_id == import_data.group_id)
    )
    total_count = count_result.scalar()
    await db.execute(
        update(KeywordGroup)
        .where(KeywordGroup.id == import_data.group_id)
        .values(total_keywords=total_count)
    )

    await db.commit()

    return {
        "message": f"导入完成，新增 {created_count} 个关键词",
        "created_count": created_count
    }


@router.post("/test-match")
async def test_keywords_match(
    request_data: KeywordTestMatchRequest,
    db: AsyncSession = Depends(get_db),
):
    """测试关键词匹配"""
    from app.services.keyword_matcher import KeywordMatcher
    matcher = KeywordMatcher()

    results = await matcher.test_keywords(request_data.text, request_data.keyword_ids)
    return {"matched": results}
