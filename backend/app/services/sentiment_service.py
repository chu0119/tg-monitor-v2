"""情感分析服务"""
from typing import List, Dict
from datetime import datetime, timedelta
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

try:
    import jieba
    import snownlp
    SENTIMENT_AVAILABLE = True
except ImportError:
    SENTIMENT_AVAILABLE = False

from app.core.database import AsyncSessionLocal
from app.models.message import Message


class SentimentService:
    """情感分析服务"""

    def __init__(self):
        self.positive_words = {
            '好', '优秀', '棒', '赞', '喜欢', '爱', '开心', '快乐', '高兴',
            '满意', '不错', '厉害', '牛', '强', '成功', '胜利', '赢', '收获',
            'good', 'great', 'awesome', 'excellent', 'love', 'like', 'happy',
            'best', 'amazing', 'wonderful', 'perfect', 'thanks', 'thank you'
        }

        self.negative_words = {
            '坏', '差', '烂', '讨厌', '恨', '烦', '生气', '愤怒', '难过',
            '失望', '糟糕', '垃圾', '废物', '失败', '输', '错', '问题',
            'bad', 'terrible', 'hate', 'angry', 'sad', 'disappointed', 'fail',
            'error', 'wrong', 'problem', 'issue', 'worst', 'sucks'
        }

    async def analyze_message_sentiment(
        self,
        db: AsyncSession,
        message_id: int
    ) -> Dict[str, any]:
        """分析单条消息的情感"""
        result = await db.execute(
            select(Message).where(Message.id == message_id)
        )
        message = result.scalar_one_or_none()

        if not message or not message.text:
            return {"sentiment": "neutral", "score": 0.5, "confidence": 0}

        text = message.text

        if SENTIMENT_AVAILABLE:
            try:
                s = snownlp.SnowNLP(text)
                score = s.sentiments

                if score > 0.6:
                    sentiment = "positive"
                elif score < 0.4:
                    sentiment = "negative"
                else:
                    sentiment = "neutral"

                return {
                    "sentiment": sentiment,
                    "score": score,
                    "confidence": abs(score - 0.5) * 2
                }
            except Exception as e:
                logger.error(f"情感分析失败: {e}")
                return self._fallback_sentiment_analysis(text)

        return self._fallback_sentiment_analysis(text)

    def _fallback_sentiment_analysis(self, text: str) -> Dict[str, any]:
        """备用情感分析（基于关键词）"""
        text_lower = text.lower()

        positive_count = sum(1 for word in self.positive_words if word in text_lower)
        negative_count = sum(1 for word in self.negative_words if word in text_lower)

        total = positive_count + negative_count

        if total == 0:
            return {"sentiment": "neutral", "score": 0.5, "confidence": 0.2}

        if positive_count > negative_count:
            score = 0.5 + (positive_count / total) * 0.5
            sentiment = "positive"
        elif negative_count > positive_count:
            score = 0.5 - (negative_count / total) * 0.5
            sentiment = "negative"
        else:
            score = 0.5
            sentiment = "neutral"

        return {
            "sentiment": sentiment,
            "score": score,
            "confidence": min(total / 10, 1)
        }

    async def analyze_conversation_sentiment(
        self,
        db: AsyncSession,
        conversation_id: int,
        days: int = 7
    ) -> Dict[str, any]:
        """分析会话的整体情感倾向"""
        start_date = datetime.now() - timedelta(days=days)

        result = await db.execute(
            select(Message).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.date >= start_date,
                    Message.text.isnot(None)
                )
            )
        )
        messages = result.scalars().all()

        if not messages:
            return {
                "positive_count": 0,
                "negative_count": 0,
                "neutral_count": 0,
                "average_score": 0.5,
                "total_messages": 0
            }

        sentiments = []
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        for msg in messages:
            if not msg.text:
                continue

            if SENTIMENT_AVAILABLE:
                try:
                    s = snownlp.SnowNLP(msg.text)
                    score = s.sentiments

                    if score > 0.6:
                        positive_count += 1
                    elif score < 0.4:
                        negative_count += 1
                    else:
                        neutral_count += 1

                    sentiments.append(score)
                except Exception as e:
                    logger.warning(f"分析消息情感失败: {e}")
                    # 使用备用分析方法
                    fallback = self._fallback_sentiment_analysis(msg.text)
                    sentiments.append(fallback["score"])
                    if fallback["sentiment"] == "positive":
                        positive_count += 1
                    elif fallback["sentiment"] == "negative":
                        negative_count += 1
                    else:
                        neutral_count += 1

        average_score = sum(sentiments) / len(sentiments) if sentiments else 0.5

        return {
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "average_score": average_score,
            "total_messages": len(sentiments)
        }

    async def get_sentiment_trend(
        self,
        db: AsyncSession,
        conversation_id: int,
        days: int = 30
    ) -> List[Dict[str, any]]:
        """获取情感趋势"""
        start_date = datetime.now() - timedelta(days=days)

        result = await db.execute(
            select(Message).where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.date >= start_date,
                    Message.text.isnot(None)
                )
            ).order_by(Message.date)
        )
        messages = result.scalars().all()

        trend_dict = {}
        for msg in messages:
            day = msg.date.strftime("%Y-%m-%d")
            if day not in trend_dict:
                trend_dict[day] = {"positive": 0, "negative": 0, "neutral": 0, "total": 0, "score_sum": 0}

            if SENTIMENT_AVAILABLE:
                try:
                    s = snownlp.SnowNLP(msg.text)
                    score = s.sentiments

                    if score > 0.6:
                        trend_dict[day]["positive"] += 1
                    elif score < 0.4:
                        trend_dict[day]["negative"] += 1
                    else:
                        trend_dict[day]["neutral"] += 1

                    trend_dict[day]["score_sum"] += score
                    trend_dict[day]["total"] += 1
                except Exception as e:
                    logger.warning(f"分析情感趋势失败: {e}")
                    # 使用备用分析方法
                    fallback = self._fallback_sentiment_analysis(msg.text)
                    if fallback["sentiment"] == "positive":
                        trend_dict[day]["positive"] += 1
                    elif fallback["sentiment"] == "negative":
                        trend_dict[day]["negative"] += 1
                    else:
                        trend_dict[day]["neutral"] += 1
                    trend_dict[day]["score_sum"] += fallback["score"]
                    trend_dict[day]["total"] += 1

        return [
            {
                "date": k,
                "positive": v["positive"],
                "negative": v["negative"],
                "neutral": v["neutral"],
                "average_score": v["score_sum"] / v["total"] if v["total"] > 0 else 0.5
            }
            for k, v in sorted(trend_dict.items())
        ]


sentiment_service = SentimentService()
