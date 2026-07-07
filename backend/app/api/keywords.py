"""关键词管理 API"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update, delete, func, text
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
from app.models.message import Message

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

    # 批量查询所有组的关键词数量 - 子查询替代N+1
    group_ids = [g.id for g in groups]
    if group_ids:
        placeholders = ",".join([f":gid{i}" for i in range(len(group_ids))])
        gid_params = {f"gid{i}": gid for i, gid in enumerate(group_ids)}
        kw_counts_result = await db.execute(text(f"""
            SELECT group_id, COUNT(*) as cnt FROM keywords
            WHERE group_id IN ({placeholders})
            GROUP BY group_id
        """), gid_params)
        kw_counts = {row[0]: row[1] for row in kw_counts_result.fetchall()}
    else:
        kw_counts = {}

    groups_list = []
    for group in groups:
        actual_count = kw_counts.get(group.id, 0)

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


@router.get("/quality-report")
async def keyword_quality_report(db: AsyncSession = Depends(get_db)):
    """关键词质量报告：重复、长期无命中、正则错误等。"""
    groups_result = await db.execute(select(KeywordGroup))
    groups = {group.id: group for group in groups_result.scalars().all()}

    keywords_result = await db.execute(select(Keyword).order_by(Keyword.group_id, Keyword.word))
    keywords = keywords_result.scalars().all()

    seen_global = {}
    duplicates_global = []
    duplicates_in_group = []
    regex_errors = []
    inactive_groups_used = []
    zero_match_keywords = []

    seen_in_group = {}
    import re
    for keyword in keywords:
        normalized = (keyword.word or "").strip().lower()
        group = groups.get(keyword.group_id)
        if not normalized:
            continue

        global_key = normalized
        if global_key in seen_global:
            duplicates_global.append({
                "word": keyword.word,
                "keyword_id": keyword.id,
                "duplicate_of": seen_global[global_key],
                "group_id": keyword.group_id,
            })
        else:
            seen_global[global_key] = keyword.id

        group_key = (keyword.group_id, normalized)
        if group_key in seen_in_group:
            duplicates_in_group.append({
                "word": keyword.word,
                "keyword_id": keyword.id,
                "duplicate_of": seen_in_group[group_key],
                "group_id": keyword.group_id,
            })
        else:
            seen_in_group[group_key] = keyword.id

        match_type = keyword.match_type or (group.match_type if group else "contains")
        if match_type == "regex":
            try:
                re.compile(keyword.word)
            except re.error as e:
                regex_errors.append({"keyword_id": keyword.id, "word": keyword.word, "error": str(e)})

        if group and not group.is_active and keyword.is_active:
            inactive_groups_used.append({"keyword_id": keyword.id, "word": keyword.word, "group_id": group.id, "group_name": group.name})

        if (keyword.match_count or 0) == 0 and keyword.is_active:
            zero_match_keywords.append({"keyword_id": keyword.id, "word": keyword.word, "group_id": keyword.group_id})

    return {
        "total_keywords": len(keywords),
        "total_groups": len(groups),
        "duplicates_global": duplicates_global[:200],
        "duplicates_in_group": duplicates_in_group[:200],
        "regex_errors": regex_errors[:200],
        "inactive_group_keywords": inactive_groups_used[:200],
        "zero_match_keywords": zero_match_keywords[:500],
        "recommendations": [
            "优先清理同组重复关键词，避免同一消息产生重复告警",
            "检查正则错误关键词，错误正则不会命中",
            "长期零命中的关键词建议用最近消息试跑，确认是否过窄或已失效",
        ],
    }


@router.post("/import-preview")
async def preview_keyword_import(
    import_data: KeywordBatchImport,
    db: AsyncSession = Depends(get_db),
):
    """批量导入前预览：空词、重复词、已存在词、将新增数量。"""
    group = (await db.execute(
        select(KeywordGroup).where(KeywordGroup.id == import_data.group_id)
    )).scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关键词组不存在")

    existing_result = await db.execute(
        select(Keyword.word).where(Keyword.group_id == import_data.group_id)
    )
    existing_words = {str(row[0]).strip().lower() for row in existing_result.all()}

    seen = set()
    empty_count = 0
    duplicates = []
    existing = []
    to_create = []
    for raw_word in import_data.keywords:
        word = (raw_word or "").strip()
        normalized = word.lower()
        if not word:
            empty_count += 1
            continue
        if normalized in seen:
            duplicates.append(word)
            continue
        seen.add(normalized)
        if not import_data.overwrite and normalized in existing_words:
            existing.append(word)
            continue
        to_create.append(word)

    return {
        "group_id": group.id,
        "group_name": group.name,
        "overwrite": import_data.overwrite,
        "input_count": len(import_data.keywords),
        "empty_count": empty_count,
        "duplicate_count": len(duplicates),
        "existing_count": len(existing),
        "create_count": len(to_create),
        "duplicates": duplicates[:100],
        "existing": existing[:100],
        "sample_to_create": to_create[:100],
    }


@router.post("/recent-match-preview")
async def recent_match_preview(
    request_data: KeywordTestMatchRequest,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """用最近消息试跑关键词，帮助判断关键词是否过宽或过窄。"""
    from app.services.keyword_matcher import KeywordMatcher
    matcher = KeywordMatcher()

    result = await db.execute(
        select(Message)
        .where(Message.text.is_not(None))
        .order_by(Message.date.desc())
        .limit(max(1, min(limit, 500)))
    )
    messages = result.scalars().all()

    hits = []
    keyword_hit_count = {}
    for message in messages:
        text = message.text or message.caption or ""
        matched = await matcher.test_keywords(text, request_data.keyword_ids)
        if matched:
            for match in matched:
                keyword_hit_count[match["word"]] = keyword_hit_count.get(match["word"], 0) + 1
            hits.append({
                "message_id": message.id,
                "conversation_id": message.conversation_id,
                "date": message.date,
                "preview": text[:300],
                "matched": matched,
            })

    return {
        "sample_size": len(messages),
        "hit_messages": len(hits),
        "keyword_hit_count": keyword_hit_count,
        "hits": hits[:100],
    }


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

    # 先删除组下关键词关联的告警记录，再删除关键词，最后删除组
    from app.models.alert import Alert
    from sqlalchemy import delete as sa_delete

    # 获取组内所有关键词ID
    kw_result = await db.execute(
        select(Keyword.id).where(Keyword.group_id == group_id)
    )
    kw_ids = [row[0] for row in kw_result.all()]

    if kw_ids:
        # 删除这些关键词关联的告警
        await db.execute(
            sa_delete(Alert).where(Alert.keyword_id.in_(kw_ids))
        )
        # 删除关键词
        await db.execute(
            sa_delete(Keyword).where(Keyword.group_id == group_id)
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
        existing_kw_result = await db.execute(
            select(Keyword.id).where(Keyword.group_id == import_data.group_id)
        )
        existing_kw_ids = [row[0] for row in existing_kw_result.all()]
        if existing_kw_ids:
            await db.execute(
                delete(Alert).where(Alert.keyword_id.in_(existing_kw_ids))
            )
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

    await db.flush()

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
