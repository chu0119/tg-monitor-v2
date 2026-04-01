"""词云生成服务"""
import io
import base64
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

try:
    from wordcloud import WordCloud
    import jieba
    WORDCLOUD_AVAILABLE = True
except ImportError:
    WORDCLOUD_AVAILABLE = False

from app.core.database import AsyncSessionLocal
from app.models.message import Message


class WordCloudService:
    """词云生成服务"""

    def __init__(self):
        self.stopwords = self._load_stopwords()

    def _load_stopwords(self) -> set:
        """加载停用词"""
        stopwords = {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一',
            '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有',
            '看', '好', '自己', '这', '那', '里', '就是', '这个', '那个', '什么',
            '可以', '但是', '因为', '所以', '如果', '或者', '虽然', '然后', '还是',
            '啊', '吗', '呢', '吧', '哦', '嗯', '哈', '啦', '呀', '哇', '唉',
            'the', 'is', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'as', 'it', 'this', 'that',
            'https', 'http', 'com', 'www', 'org', 'net', 'io', 'co', 'ru'
        }
        return stopwords

    async def generate_wordcloud(
        self,
        db: AsyncSession,
        conversation_id: Optional[int] = None,
        sender_id: Optional[int] = None,
        days: int = 7,
        width: int = 800,
        height: int = 400,
        max_words: int = 100
    ) -> Optional[str]:
        """生成词云并返回 base64 编码的图片"""
        if not WORDCLOUD_AVAILABLE:
            return None

        texts = await self._get_message_texts(db, conversation_id, sender_id, days)
        if not texts:
            return None

        word_freq = self._analyze_texts(texts)
        if not word_freq:
            return None

        try:
            wordcloud = WordCloud(
                width=width,
                height=height,
                background_color='rgba(0,0,0,0)',
                colormap='viridis',
                max_words=max_words,
                relative_scaling=0.5,
                min_font_size=10,
                prefer_horizontal=0.7,
                font_path=None  # 使用默认字体
            ).generate_from_frequencies(dict(word_freq))

            img_buffer = io.BytesIO()
            wordcloud.to_image().save(img_buffer, format='PNG')
            img_buffer.seek(0)
            img_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')

            return f"data:image/png;base64,{img_base64}"

        except Exception as e:
            logger.error(f"生成词云失败: {e}")
            return None

    async def _get_message_texts(
        self,
        db: AsyncSession,
        conversation_id: Optional[int],
        sender_id: Optional[int],
        days: int
    ) -> List[str]:
        """获取消息文本"""
        start_date = datetime.now() - timedelta(days=days)

        query = select(Message.text).where(
            and_(
                Message.date >= start_date,
                Message.text.isnot(None),
                Message.text != ''
            )
        )

        if conversation_id:
            query = query.where(Message.conversation_id == conversation_id)
        if sender_id:
            query = query.where(Message.sender_id == sender_id)

        result = await db.execute(query)
        texts = [row[0] for row in result.all()]
        return texts

    def _analyze_texts(self, texts: List[str]) -> Tuple[Tuple[str, int], ...]:
        """分析文本并返回词频统计"""
        word_freq = {}

        for text in texts:
            try:
                words = jieba.cut(text)
                for word in words:
                    word = word.strip()
                    if (
                        len(word) < 2 or
                        word in self.stopwords or
                        word.isdigit() or
                        any(c.isdigit() for c in word)
                    ):
                        continue
                    word_freq[word] = word_freq.get(word, 0) + 1
            except Exception:
                continue

        return tuple(sorted(word_freq.items(), key=lambda x: x[1], reverse=True))

    async def get_top_words(
        self,
        db: AsyncSession,
        conversation_id: Optional[int] = None,
        sender_id: Optional[int] = None,
        days: int = 7,
        limit: int = 50
    ) -> List[dict]:
        """获取高频词列表"""
        texts = await self._get_message_texts(db, conversation_id, sender_id, days)
        if not texts:
            return []

        word_freq = self._analyze_texts(texts)
        return [
            {"word": word, "count": count}
            for word, count in word_freq[:limit]
        ]

    async def get_keyword_trend(
        self,
        db: AsyncSession,
        keyword: str,
        days: int = 30,
        interval: str = "day"
    ) -> List[dict]:
        """获取关键词出现趋势"""
        start_date = datetime.now() - timedelta(days=days)

        # 获取包含关键词的消息
        query = select(Message).where(
            and_(
                Message.date >= start_date,
                Message.text.ilike(f'%{keyword}%')
            )
        ).order_by(Message.date)

        result = await db.execute(query)
        messages = result.scalars().all()

        # 按日期分组统计
        trend_dict = {}
        for msg in messages:
            if interval == "hour":
                key = msg.date.strftime("%Y-%m-%d %H:00")
            elif interval == "week":
                key = msg.date.strftime("%Y-W%W")
            else:  # day
                key = msg.date.strftime("%Y-%m-%d")

            trend_dict[key] = trend_dict.get(key, 0) + 1

        return [
            {"time": k, "count": v}
            for k, v in sorted(trend_dict.items())
        ]


wordcloud_service = WordCloudService()
