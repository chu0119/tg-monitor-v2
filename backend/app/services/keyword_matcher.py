"""关键词匹配服务"""
import re
from functools import lru_cache
import time
from typing import List, Optional
from sqlalchemy import select, update
from loguru import logger
from app.core.database import AsyncSessionLocal
from app.models import Keyword, KeywordGroup, Conversation
from datetime import datetime



@lru_cache(maxsize=1024)
def _compile_regex(pattern: str, flags: int = 0):
    """缓存编译后的正则表达式"""
    return re.compile(pattern, flags)

class KeywordMatcher:
    """关键词匹配器"""

    def __init__(self):
        self._rules_cache = {}
        self._rules_cache_times = {}
        self._cache_ttl = 30

    def invalidate_cache(self):
        self._rules_cache.clear()

    def _cache_key(self, group_ids: Optional[list], enable_all_keywords: bool) -> tuple:
        if enable_all_keywords or not group_ids:
            return ("all",)
        return tuple(sorted(int(gid) for gid in group_ids))

    async def _get_keyword_rules(self, db, group_ids: Optional[list], enable_all_keywords: bool) -> List[dict]:
        key = self._cache_key(group_ids, enable_all_keywords)
        cached = self._rules_cache.get(key)
        if cached and time.time() - cached["created_at"] < self._cache_ttl:
            return cached["rules"]

        query = (
            select(Keyword, KeywordGroup)
            .join(KeywordGroup, Keyword.group_id == KeywordGroup.id)
            .where(Keyword.is_active == True, KeywordGroup.is_active == True)
        )
        if group_ids and not enable_all_keywords:
            query = query.where(Keyword.group_id.in_(group_ids))

        result = await db.execute(query)
        rules = []
        for keyword, group in result.all():
            rules.append({
                "keyword_id": keyword.id,
                "word": keyword.word,
                "group_id": group.id,
                "group_name": group.name,
                "match_type": keyword.match_type or group.match_type,
                "case_sensitive": keyword.case_sensitive if keyword.case_sensitive is not None else group.case_sensitive,
                "alert_level": keyword.alert_level or group.alert_level,
                "synonyms": keyword.synonyms if hasattr(keyword, 'synonyms') and keyword.synonyms else [],
            })

        self._rules_cache[key] = {"created_at": time.time(), "rules": rules}
        return rules

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

        group_ids = conversation.keyword_groups
        rules = await self._get_keyword_rules(db, group_ids, conversation.enable_all_keywords)

        # 执行匹配
        matched = []
        for rule in rules:
            # 执行匹配
            if self._match(text, rule["word"], rule["match_type"], rule["case_sensitive"]):
                matched.append({
                    "keyword_id": rule["keyword_id"],
                    "word": rule["word"],
                    "group_id": rule["group_id"],
                    "group_name": rule["group_name"],
                    "alert_level": rule["alert_level"],
                    "match_type": rule["match_type"],
                })

                # 更新关键词匹配统计 - 使用 SQLAlchemy update 语句确保持久化
                await db.execute(
                    update(Keyword)
                    .where(Keyword.id == rule["keyword_id"])
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
                return bool(_compile_regex(keyword, flags).search(text))
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
        keyword_ids: Optional[List[int]] = None
    ) -> List[dict]:
        """测试关键词匹配"""
        async with AsyncSessionLocal() as db:
            if keyword_ids:
                result = await db.execute(
                    select(Keyword).where(Keyword.id.in_(keyword_ids))
                )
            else:
                result = await db.execute(
                    select(Keyword).where(Keyword.is_active == True)
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
            matched_ids = set()
            for keyword in keywords:
                group = groups_map.get(keyword.group_id)

                if group:
                    match_type = keyword.match_type or group.match_type
                    case_sensitive = keyword.case_sensitive if keyword.case_sensitive is not None else group.case_sensitive

                    # 主词 + 同义词
                    words_to_check = [keyword.word]
                    synonyms = getattr(keyword, 'synonyms', None) or []
                    if synonyms:
                        words_to_check.extend(synonyms)

                    for w in words_to_check:
                        if self._match(text, w, match_type, case_sensitive):
                            if keyword.id not in matched_ids:
                                matched_ids.add(keyword.id)
                                matched.append({
                                    "keyword_id": keyword.id,
                                    "word": keyword.word,
                                    "group_id": group.id,
                                    "group_name": group.name,
                                    "match_type": match_type,
                                })
                            break

            return matched
