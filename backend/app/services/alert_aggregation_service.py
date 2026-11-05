"""告警聚合服务 - 短时间内相同来源的告警自动合并"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.models.alert import Alert
from app.utils import now_utc


class AlertAggregationService:
    """告警聚合服务

    功能：
    1. 聚合窗口：同一会话+同一关键词组在窗口期内的告警自动合并
    2. 告警升级：未处理的告警随时间自动提升级别
    3. 聚合统计：按时间段/来源/级别统计告警趋势
    """

    # 默认聚合窗口（分钟）
    DEFAULT_AGGREGATION_WINDOW = 30

    # 告警升级规则（小时 -> 升级后级别）。级别序：low < medium < high < critical
    ESCALATION_RULES = {
        24: "medium",    # 24小时未处理 -> 至少 medium
        48: "high",      # 48小时未处理 -> 至少 high
        72: "critical",  # 72小时未处理 -> 至少 critical
    }
    _LEVEL_ORDER = ["low", "medium", "high", "critical"]

    async def get_aggregated_alerts(
        self,
        db: AsyncSession,
        window_minutes: int = None,
        status: Optional[str] = None,
    ) -> List[Dict]:
        """获取聚合后的告警摘要

        将同一会话+同一关键词组在窗口期内的告警合并为一条摘要
        """
        if window_minutes is None:
            window_minutes = self.DEFAULT_AGGREGATION_WINDOW

        cutoff = now_utc() - timedelta(minutes=window_minutes)

        # 查询最近窗口期内的待处理告警，按会话和关键词组分组
        conditions = [Alert.created_at >= cutoff]
        if status:
            conditions.append(Alert.status == status)
        else:
            conditions.append(Alert.status == "pending")

        result = await db.execute(
            select(
                Alert.conversation_id,
                Alert.keyword_group_name,
                func.count(Alert.id).label("count"),
                func.min(Alert.created_at).label("first_alert"),
                func.max(Alert.created_at).label("last_alert"),
                func.group_concat(Alert.id).label("alert_ids"),  # MySQL 专有函数，项目使用 MySQL
            )
            .where(and_(*conditions))
            .group_by(Alert.conversation_id, Alert.keyword_group_name)
            .order_by(func.count(Alert.id).desc())
        )

        groups = result.all()

        summaries = []
        for group in groups:
            # GROUP_CONCAT 返回逗号分隔的字符串，需要转为 int 列表
            alert_id_list = [int(x) for x in group.alert_ids.split(",")] if group.alert_ids else []

            # 获取最新一条告警的详细信息
            latest_result = await db.execute(
                select(Alert).where(
                    Alert.id.in_(alert_id_list)
                ).order_by(Alert.created_at.desc()).limit(1)
            )
            latest = latest_result.scalar_one_or_none()

            summaries.append({
                "conversation_id": group.conversation_id,
                "keyword_group_name": group.keyword_group_name,
                "count": group.count,
                "first_alert": group.first_alert.isoformat() if group.first_alert else None,
                "last_alert": group.last_alert.isoformat() if group.last_alert else None,
                "alert_ids": alert_id_list,
                "latest_alert_level": latest.alert_level if latest else None,
                "latest_preview": (latest.message_preview or "")[:200] if latest else None,
            })

        return summaries

    async def escalate_stale_alerts(self, db: AsyncSession) -> Dict:
        """升级超时未处理的告警

        根据创建时间和升级规则，自动**提升**告警级别（只升不降：
        原实现按 24/48/72h 顺序执行且只判断 alert_level != new_level，
        会把已创建为 critical 的告警降级成 medium）。
        """
        escalated = 0
        now = now_utc()

        # 从高到低处理：72h 先升级到 critical，之后低档规则排除已达高级别的告警
        sorted_rules = sorted(self.ESCALATION_RULES.items(), key=lambda x: x[0], reverse=True)
        higher_levels: List[str] = []

        for hours, target_level in sorted_rules:
            cutoff = now - timedelta(hours=hours)
            # 排除目标级别本身以及更高级别（已是 high/critical 的不能被 24h 规则拉回 medium）
            excluded = set(higher_levels) | {target_level}
            result = await db.execute(
                update(Alert)
                .where(
                    and_(
                        Alert.status == "pending",
                        Alert.created_at < cutoff,
                        Alert.alert_level.notin_(excluded),
                    )
                )
                .values(alert_level=target_level)
            )
            count = result.rowcount or 0
            if count > 0:
                escalated += count
                logger.info(f"告警升级: {count} 条超过 {hours}h 的告警 -> {target_level}")
            higher_levels.append(target_level)

        if escalated > 0:
            await db.commit()

        return {
            "escalated_count": escalated,
            "message": f"已升级 {escalated} 条超时告警"
        }

    async def get_alert_trend(
        self,
        db: AsyncSession,
        days: int = 7,
        group_by: str = "day",
    ) -> List[Dict]:
        """获取告警趋势统计

        Args:
            days: 统计天数
            group_by: 分组方式 (day/hour)
        """
        cutoff = now_utc() - timedelta(days=days)

        if group_by == "hour":
            date_format = "%Y-%m-%d %H:00"
        else:
            date_format = "%Y-%m-%d"

        # MySQL 使用 DATE_FORMAT
        result = await db.execute(
            select(
                func.date_format(Alert.created_at, date_format).label("period"),
                Alert.alert_level,
                func.count(Alert.id).label("count"),
            )
            .where(Alert.created_at >= cutoff)
            .group_by(
                func.date_format(Alert.created_at, date_format),
                Alert.alert_level,
            )
            .order_by("period")
        )

        rows = result.all()

        trend = []
        for row in rows:
            trend.append({
                "period": row.period,
                "alert_level": row.alert_level,
                "count": row.count,
            })

        return trend


# 全局实例
alert_aggregation_service = AlertAggregationService()
