"""自动化报告生成服务"""
import io
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logger.warning("ReportLab not installed. Install with: pip install reportlab")

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from app.core.database import AsyncSessionLocal
from app.models import Message, Alert, Conversation, KeywordGroup, Sender
from app.services.wordcloud_service import wordcloud_service
from app.services.sentiment_service import sentiment_service


class ReportService:
    """报告生成服务"""

    async def generate_daily_report(
        self,
        db: AsyncSession,
        date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """生成日报数据"""
        if date is None:
            date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        next_date = date + timedelta(days=1)

        # 统计数据
        total_messages = await db.execute(
            select(func.count(Message.id))
            .where(and_(Message.date >= date, Message.date < next_date))
        )
        total_messages = total_messages.scalar()

        total_alerts = await db.execute(
            select(func.count(Alert.id))
            .where(and_(Alert.created_at >= date, Alert.created_at < next_date))
        )
        total_alerts = total_alerts.scalar()

        # 获取活跃会话
        active_conversations = await db.execute(
            select(Conversation)
            .where(Conversation.status == "active")
        )
        active_conversations = active_conversations.scalars().all()

        # 获取今日告警详情
        alerts_result = await db.execute(
            select(Alert)
            .where(and_(Alert.created_at >= date, Alert.created_at < next_date))
            .order_by(Alert.created_at.desc())
            .limit(100)
        )
        alerts = alerts_result.scalars().all()

        # 按级别统计告警
        alert_by_level = {}
        for alert in alerts:
            level = alert.alert_level
            alert_by_level[level] = alert_by_level.get(level, 0) + 1

        return {
            "report_date": date.strftime("%Y-%m-%d"),
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_messages": total_messages,
                "total_alerts": total_alerts,
                "active_conversations": len(active_conversations),
                "alert_by_level": alert_by_level
            },
            "top_alerts": [
                {
                    "keyword": alert.keyword_text,
                    "keyword_group": alert.keyword_group_name,
                    "alert_level": alert.alert_level,
                    "message_preview": alert.message_preview[:100],
                    "created_at": alert.created_at.isoformat()
                }
                for alert in alerts[:20]
            ]
        }

    async def generate_weekly_report(
        self,
        db: AsyncSession,
        start_date: Optional[datetime] = None
    ) -> Dict[str, any]:
        """生成周报数据"""
        if start_date is None:
            start_date = datetime.now() - timedelta(days=7)

        end_date = datetime.now()

        # 消息统计
        message_stats = await db.execute(
            select(
                func.date_trunc('day', Message.date).label('day'),
                func.count(Message.id).label('count')
            )
            .where(and_(Message.date >= start_date, Message.date < end_date))
            .group_by(func.date_trunc('day', Message.date))
        )
        message_stats = message_stats.all()

        # 告警统计
        alert_stats = await db.execute(
            select(
                func.date_trunc('day', Alert.created_at).label('day'),
                func.count(Alert.id).label('count')
            )
            .where(and_(Alert.created_at >= start_date, Alert.created_at < end_date))
            .group_by(func.date_trunc('day', Alert.created_at))
        )
        alert_stats = alert_stats.all()

        # 热门关键词组
        top_groups = await db.execute(
            select(Alert.keyword_group_name, func.count(Alert.id).label('count'))
            .where(and_(Alert.created_at >= start_date, Alert.created_at < end_date))
            .group_by(Alert.keyword_group_name)
            .order_by(func.count(Alert.id).desc())
            .limit(10)
        )
        top_groups = top_groups.all()

        # 活跃发送者
        top_senders = await db.execute(
            select(Sender, func.count(Message.id).label('count'))
            .join(Message)
            .where(and_(Message.date >= start_date, Message.date < end_date))
            .group_by(Sender.id)
            .order_by(func.count(Message.id).desc())
            .limit(10)
        )
        top_senders = top_senders.all()

        return {
            "report_period": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
            "generated_at": datetime.now().isoformat(),
            "message_trend": [
                {"date": stat.day.strftime("%Y-%m-%d"), "count": stat.count}
                for stat in message_stats
            ],
            "alert_trend": [
                {"date": stat.day.strftime("%Y-%m-%d"), "count": stat.count}
                for stat in alert_stats
            ],
            "top_keyword_groups": [
                {"name": group, "count": count} for group, count in top_groups
            ],
            "top_senders": [
                {
                    "username": sender.username or sender.first_name,
                    "message_count": count
                }
                for sender, count in top_senders
            ]
        }

    async def generate_pdf_report(
        self,
        db: AsyncSession,
        report_type: str = "daily",
        start_date: Optional[datetime] = None
    ) -> Optional[bytes]:
        """生成 PDF 报告

        Returns:
            PDF 文件的字节内容，如果 ReportLab 未安装则返回 None
        """
        if not REPORTLAB_AVAILABLE:
            return None

        buffer = io.BytesIO()

        # 创建 PDF
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=18
        )

        # 样式
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#00f0ff'),
            spaceAfter=30,
            alignment=TA_CENTER
        )

        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#b026ff'),
            spaceAfter=12
        )

        # 内容容器
        story = []

        # 标题
        if report_type == "daily":
            report_data = await self.generate_daily_report(db, start_date)
            title = f"日报 - {report_data['report_date']}"
        else:
            report_data = await self.generate_weekly_report(db, start_date)
            title = f"周报 - {report_data['report_period']}"

        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))

        # 生成时间
        story.append(Paragraph(
            f"<b>生成时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            styles['Normal']
        ))
        story.append(Spacer(1, 20))

        # 统计摘要
        story.append(Paragraph("统计摘要", heading_style))

        if report_type == "daily":
            summary = report_data['summary']
            summary_data = [
                ["指标", "数值"],
                ["总消息数", str(summary['total_messages'])],
                ["总告警数", str(summary['total_alerts'])],
                ["活跃会话数", str(summary['active_conversations'])],
            ]

            # 添加告警级别统计
            for level, count in summary.get('alert_by_level', {}).items():
                summary_data.append([f"{level}级告警", str(count)])

        else:
            weekly_data = report_data
            total_messages = sum(d['count'] for d in weekly_data['message_trend'])
            total_alerts = sum(d['count'] for d in weekly_data['alert_trend'])

            summary_data = [
                ["指标", "数值"],
                ["总消息数", str(total_messages)],
                ["总告警数", str(total_alerts)],
            ]

        # 创建表格
        table = Table(summary_data, colWidths=[3 * inch, 2 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#00f0ff')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f0f0f0')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        story.append(table)
        story.append(Spacer(1, 20))

        # 生成图表（如果 matplotlib 可用）
        if MATPLOTLIB_AVAILABLE and report_type == "weekly":
            chart_image = await self._generate_trend_chart(report_data)
            if chart_image:
                story.append(Paragraph("趋势图表", heading_style))
                story.append(Image(chart_image, width=5 * inch, height=3 * inch))
                story.append(Spacer(1, 20))

        # 生成 PDF
        doc.build(story)
        buffer.seek(0)

        return buffer.read()

    async def _generate_trend_chart(self, report_data: Dict) -> Optional[io.BytesIO]:
        """生成趋势图表"""
        if not MATPLOTLIB_AVAILABLE:
            return None

        try:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6))

            # 消息趋势
            message_trend = report_data.get('message_trend', [])
            if message_trend:
                dates = [d['date'] for d in message_trend]
                counts = [d['count'] for d in message_trend]

                ax1.plot(dates, counts, marker='o', color='#00f0ff', linewidth=2)
                ax1.set_title('消息趋势', fontsize=12, color='#00f0ff')
                ax1.set_ylabel('消息数')
                ax1.grid(True, alpha=0.3)
                ax1.tick_params(axis='x', rotation=45)

            # 告警趋势
            alert_trend = report_data.get('alert_trend', [])
            if alert_trend:
                dates = [d['date'] for d in alert_trend]
                counts = [d['count'] for d in alert_trend]

                ax2.bar(dates, counts, color='#ff006e', alpha=0.7)
                ax2.set_title('告警趋势', fontsize=12, color='#ff006e')
                ax2.set_ylabel('告警数')
                ax2.grid(True, alpha=0.3)
                ax2.tick_params(axis='x', rotation=45)

            plt.tight_layout()

            # 保存到 BytesIO
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', dpi=100, facecolor='#1a1a2e')
            buffer.seek(0)
            plt.close()

            return buffer
        except Exception as e:
            logger.error(f"生成图表失败: {e}")
            return None


# 全局报告服务实例
report_service = ReportService()
