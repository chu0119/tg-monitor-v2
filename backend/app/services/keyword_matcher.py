"""关键词匹配服务"""
import re
from typing import List, Optional
from sqlalchemy import select, update
from loguru import logger
from app.core.database import AsyncSessionLocal
from app.models import Keyword, KeywordGroup, Conversation
from datetime import datetime


class KeywordMatcher:
    """关键词匹配器"""

    async def match_message(
        self,
        db: AsyncSessionLocal,
        message,
        conversation_id: int
    ) -> List[dict]:
        """匹配消息中的关键词"""
        # 获取消息文本
        text = message.text or getattr(message, "caption", None) or ""
        if not text:
            return []

        # 获取会话配置的关键词组
        result = await db.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            return []

        # 确定要使用的关键词组
        if conversation.enable_all_keywords:
            # 使用所有激活的关键词
            keyword_result = await db.execute(
                select(Keyword).where(Keyword.is_active == True)
            )
        else:
            # 使用指定关键词组
            group_ids = conversation.keyword_groups
            if not group_ids:
                # 如果没有指定关键词组，默认使用所有激活的关键词组
                # 这样用户无需为每个会话手动配置关键词组
                keyword_result = await db.execute(
                    select(Keyword).where(Keyword.is_active == True)
                )
            else:
                keyword_result = await db.execute(
                    select(Keyword).where(
                        Keyword.group_id.in_(group_ids),
                        Keyword.is_active == True
                    )
                )

        keywords = keyword_result.scalars().all()

        # 预加载所有相关关键词组，避免 N+1 查询
        group_ids_in_keywords = list(set(k.group_id for k in keywords if k.group_id))
        groups_map = {}
        if group_ids_in_keywords:
            groups_result = await db.execute(
                select(KeywordGroup).where(KeywordGroup.id.in_(group_ids_in_keywords))
            )
            groups_map = {g.id: g for g in groups_result.scalars().all()}

        # 执行匹配
        matched = []
        for keyword in keywords:
            # 从预加载的 map 中获取关键词组配置
            group = groups_map.get(keyword.group_id)
            if not group or not group.is_active:
                continue

            # 使用关键词级别的配置或组级别的配置
            match_type = keyword.match_type or group.match_type
            case_sensitive = keyword.case_sensitive if keyword.case_sensitive is not None else group.case_sensitive
            alert_level = keyword.alert_level or group.alert_level

            # 执行匹配
            if self._match(text, keyword.word, match_type, case_sensitive):
                matched.append({
                    "keyword_id": keyword.id,
                    "word": keyword.word,
                    "group_id": group.id,
                    "group_name": group.name,
                    "alert_level": alert_level,
                    "match_type": match_type,
                })

                # 更新关键词匹配统计 - 使用 SQLAlchemy update 语句确保持久化
                await db.execute(
                    update(Keyword)
                    .where(Keyword.id == keyword.id)
                    .values(
                        match_count=Keyword.match_count + 1,
                        last_matched_at=message.date
                    )
                )

        # 更新关键词组统计 - 使用 SQLAlchemy update 语句确保持久化
        # 收集需要更新的组ID，避免重复更新
        group_ids_to_update = {}
        for match in matched:
            group_id = match["group_id"]
            if group_id not in group_ids_to_update:
                group_ids_to_update[group_id] = 0
            group_ids_to_update[group_id] += 1

        # 批量更新关键词组统计
        for group_id, increment in group_ids_to_update.items():
            await db.execute(
                update(KeywordGroup)
                .where(KeywordGroup.id == group_id)
                .values(total_matches=KeywordGroup.total_matches + increment)
            )

        return matched

    def _match(self, text: str, keyword: str, match_type: str, case_sensitive: bool) -> bool:
        """执行单个关键词匹配"""
        if not case_sensitive:
            text = text.lower()
            keyword = keyword.lower()

        if match_type == "exact":
            # 精确匹配
            return keyword == text

        elif match_type == "contains":
            # 包含匹配
            return keyword in text

        elif match_type == "regex":
            # 正则匹配
            try:
                flags = 0 if case_sensitive else re.IGNORECASE
                return bool(re.search(keyword, text, flags))
            except re.error:
                logger.warning(f"正则表达式错误: {keyword}")
                return False

        elif match_type == "fuzzy":
            # 模糊匹配（简单实现，可以集成 fuzzywuzzy）
            # 这里使用简单的子串匹配
            return keyword in text

        return False

    async def test_keywords(
        self,
        text: str,
        keyword_ids: List[int]
    ) -> List[dict]:
        """测试关键词匹配"""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Keyword).where(Keyword.id.in_(keyword_ids))
            )
            keywords = result.scalars().all()

            # 预加载关键词组
            group_ids_in_keywords = list(set(k.group_id for k in keywords if k.group_id))
            groups_map = {}
            if group_ids_in_keywords:
                groups_result = await db.execute(
                    select(KeywordGroup).where(KeywordGroup.id.in_(group_ids_in_keywords))
                )
                groups_map = {g.id: g for g in groups_result.scalars().all()}

            matched = []
            for keyword in keywords:
                group = groups_map.get(keyword.group_id)

                if group:
                    match_type = keyword.match_type or group.match_type
                    case_sensitive = keyword.case_sensitive if keyword.case_sensitive is not None else group.case_sensitive

                    if self._match(text, keyword.word, match_type, case_sensitive):
                        matched.append({
                            "keyword_id": keyword.id,
                            "word": keyword.word,
                            "group_id": group.id,
                            "group_name": group.name,
                            "match_type": match_type,
                        })

            return matched
