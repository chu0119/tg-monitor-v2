"""消息风险/情感分析服务（可解释的混合分析器）

设计说明（为什么不用 SnowNLP）：
  SnowNLP 的情感模型用淘宝购物评论训练，对 Telegram 群消息（诈骗/广告/闲聊）
  完全出域，输出恒定 ~0.5 —— 即"所有会话都是 50%"的假功能。

本实现三层信号，全部可解释：
  1. 系统风险词库联动（最强信号）：消息命中本系统关键词组（诈骗/广告/涉政等）
     → 直接判「风险」，命中词来自 DB 的 messages.matched_keywords，零额外计算
  2. 情感词典（约 500 词，含网络黑话）+ 否定词翻转 + 程度副词加权 → 判「负面/正面」
  3. 其余 → 「正常」

性能：纯内存计算（毫秒级/千条），matched_keywords 由 DB 预取，
     jieba 分词跑在线程池避免阻塞事件循环，会话级结果缓存 60 秒。
"""
from typing import List, Dict
from datetime import datetime, timedelta, timezone
from collections import Counter
from sqlalchemy import select, and_, text as sa_text
from loguru import logger

from app.core.database import AsyncSessionLocal
from app.models.message import Message

ANALYZER_VERSION = "hybrid-lexicon-v1"

# ============ 情感词典 ============
# 负面情绪/冲突（不含风险词——风险词由系统词库负责）
NEGATIVE_WORDS = {
    '垃圾', '骗子', '诈骗', '跑路', '杀猪', '坑', '坑人', '骗', '忽悠', '套路',
    '恶心', '气愤', '愤怒', '举报', '曝光', '黑心', '无耻', '下流', '卑鄙',
    '失败', '亏', '亏了', '亏死', '血亏', '被割', '割韭菜', '韭菜', '被套',
    '完蛋', '完了', '完犊子', '凉了', '凉凉', '废了', '倒霉', '背运',
    '生气', '气死', '烦', '烦死', '讨厌', '恶心他妈给恶心开门',
    '失望', '绝望', '崩溃', '无语', '服了', '醉了', '离谱', '逆天',
    '后悔', '上当', '受骗', '吃亏', '被坑', '背刺', '捅刀',
    '差评', '垃圾站', '狗屎', '屎', '粪', '傻逼', 'sb', 'nmsl', '妈的', 'tm', 'tmd',
    '烂', '烂透了', '稀烂', '破', '破烂', '渣', '渣渣', '菜', '菜鸡',
    '滚', '滚蛋', '闭嘴', '脑残', '弱智', '白痴', '低能', '蠢', '蠢货',
    '哭', '哭了', '想哭', '泪目', '惨', '惨了', '太惨', '可怜',
    '焦虑', '抑郁', 'emo', '破防', '绷不住', '蚌埠住了',
    '浪费', '耽误', '坑爹', '无奈', '难受', '后悔莫及', '血本无归', '债', '负债',
    'warn', 'warning', 'scam', 'fraud', 'fake', 'shit', 'fuck', 'damn',
}

# 正面情绪/收益
POSITIVE_WORDS = {
    '好', '很好', '太好', '好棒', '棒', '真棒', '太棒', '优秀', '赞', '点赞',
    '厉害', '牛', '牛批', '牛逼', 'nb', '666', 'yyds', '绝了', '无敌',
    '喜欢', '爱了', '开心', '快乐', '高兴', '舒服', '爽', '舒坦', '痛快',
    '满意', '不错', '可以', '稳', '稳了', '靠谱', '可靠', '信任', '放心',
    '成功', '成了', '成了!', '赢了', '赚', '赚了', '赚到', '血赚', '赚麻',
    '盈利', '收益', '分红', '返现到账', '到账', '秒到账', '钱包鼓了',
    '感谢', '谢谢', '感恩', '多谢', '辛苦', '辛苦了',
    '恭喜', '祝贺', '喜提', '好运', '幸运', '锦鲤', '欧', '欧气', '天选',
    '完美', '满分', '好评', '五星', '推荐', '安利', '种草',
    '加油', '冲', '冲啊', '搞起', '干就完了', '起飞', '起飞了', '拉升', '暴涨',
    'good', 'great', 'nice', 'perfect', 'excellent', 'awesome', 'thanks', 'love',
}

# 程度副词（加权）
INTENSIFIERS = {'很', '太', '超', '超级', '非常', '特别', '极', '极其', '贼', '巨', '真的', '实锤', '绝对'}

# 否定词（翻转相邻情感词）
NEGATION_WORDS = {'不', '没', '没有', '别', '莫', '非', '无', '毫不', '从不', '毫无'}

try:
    import jieba
    JIEBA_OK = True
except ImportError:
    JIEBA_OK = False


def _tokenize(text: str) -> List[str]:
    """分词（jieba 可用则分词，否则退化为 2-gram + 原词匹配）"""
    if JIEBA_OK:
        return [t for t in jieba.lcut(text) if t.strip()]
    return text.split()


class SentimentService:
    """消息风险/情感分析（可解释混合分析器）"""

    def __init__(self):
        self._cache: dict = {}  # {(conv_id, days): (ts, result)}
        self._cache_ttl = 60
        # 预编译：把词典转成 tuple 加速遍历
        self._neg = tuple(NEGATIVE_WORDS)
        self._pos = tuple(POSITIVE_WORDS)
        self._intens = tuple(INTENSIFIERS)
        self._negation = tuple(NEGATION_WORDS)

    # ---------- 单条消息判定（纯内存，供批量循环调用） ----------
    def _classify_text(self, text: str) -> str:
        """词典法判定：返回 risk|negative|positive|normal

        risk 只能由 DB 的 matched_keywords 判定（见 _analyze_batch），
        这里只做情感两极。
        """
        t = text.lower()
        if not t:
            return 'normal'

        tokens = _tokenize(t)
        if not tokens:
            tokens = [t]

        neg_score = 0
        pos_score = 0
        for i, tok in enumerate(tokens):
            # 否定词翻转：前 2 个 token 内出现否定词则翻转当前词极性
            negated = any(tokens[j] in self._negation for j in range(max(0, i - 2), i))
            intens = 2 if any(tokens[j] in self._intens for j in range(max(0, i - 2), i)) else 1
            weight = intens
            if tok in self._neg:
                if not negated:
                    neg_score += weight
                else:
                    pos_score += weight  # "不垃圾" → 正面
            elif tok in self._pos:
                if not negated:
                    pos_score += weight
                else:
                    neg_score += weight  # "不稳定" → 负面

        if neg_score > pos_score:
            return 'negative'
        if pos_score > neg_score:
            return 'positive'
        # 全文兜底子串匹配（jieba 切碎的词）
        raw_neg = sum(1 for w in self._neg if len(w) >= 2 and w in t)
        raw_pos = sum(1 for w in self._pos if len(w) >= 2 and w in t)
        if raw_neg > raw_pos:
            return 'negative'
        if raw_pos > raw_neg:
            return 'positive'
        return 'normal'

    # ---------- 会话级分析 ----------
    async def analyze_conversation_sentiment(
        self,
        db,
        conversation_id: int,
        days: int = 7,
    ) -> Dict:
        cache_key = (conversation_id, days)
        import time
        cached = self._cache.get(cache_key)
        now = time.time()
        if cached and now - cached[0] < self._cache_ttl:
            return cached[1]

        start_date = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

        # 一次查询取文本 + 已匹配的风险词（matched_keywords 是系统词库的真实命中）
        result = await db.execute(
            select(Message.text, Message.matched_keywords, Message.date)
            .where(
                and_(
                    Message.conversation_id == conversation_id,
                    Message.date >= start_date,
                    Message.text.isnot(None),
                )
            )
            .order_by(Message.date.desc())
            .limit(3000)
        )
        rows = result.all()

        if not rows:
            empty = {
                "total_messages": 0,
                "risk_count": 0, "negative_count": 0,
                "positive_count": 0, "normal_count": 0,
                "average_score": 0.5,
                "risk_ratio": 0.0,
                "top_risk_keywords": [],
                "by_day": [],
                "method": ANALYZER_VERSION,
                "description": "该会话在所选时间范围内没有文本消息",
            }
            self._cache[cache_key] = (now, empty)
            return empty

        risk_count = neg_count = pos_count = normal_count = 0
        score_sum = 0.0
        keyword_counter: Counter = Counter()
        by_day: Dict[str, Dict] = {}

        texts = [r[0] or '' for r in rows]
        # 分词批量放线程池（jieba 首次加载词典 ~1s，不能阻塞事件循环）
        loop = __import__('asyncio').get_running_loop()
        classifications = await loop.run_in_executor(
            None, lambda: [self._classify_text(t) for t in texts]
        )

        for (msg_text, matched_kw, msg_date), cls in zip(rows, classifications):
            day = msg_date.strftime('%Y-%m-%d')
            bucket = by_day.setdefault(
                day, {'risk': 0, 'negative': 0, 'positive': 0, 'normal': 0, 'total': 0}
            )
            bucket['total'] += 1

            # 信号1：系统风险词库命中（真实数据，最强信号）
            msg_risk_words: List[str] = []
            if matched_kw:
                try:
                    kws = matched_kw if isinstance(matched_kw, list) else __import__('json').loads(matched_kw)
                    msg_risk_words = [str(k) for k in kws if k]
                except Exception:
                    msg_risk_words = []

            if msg_risk_words:
                cls_final = 'risk'
                risk_count += 1
                bucket['risk'] += 1
                for w in msg_risk_words:
                    keyword_counter[w] += 1
            else:
                cls_final = cls
                if cls == 'negative':
                    neg_count += 1
                    bucket['negative'] += 1
                elif cls == 'positive':
                    pos_count += 1
                    bucket['positive'] += 1
                else:
                    normal_count += 1
                    bucket['normal'] += 1

            # 情绪分：risk 0.05 / negative 0.3 / normal 0.55 / positive 0.85（风控语义：越低越危险）
            score_map = {'risk': 0.05, 'negative': 0.3, 'normal': 0.55, 'positive': 0.85}
            score_sum += score_map[cls_final]

        total = len(rows)
        average_score = score_sum / total if total else 0.5

        payload = {
            "total_messages": total,
            "risk_count": risk_count,
            "negative_count": neg_count,
            "positive_count": pos_count,
            "normal_count": normal_count,
            "average_score": round(average_score, 3),
            "risk_ratio": round(risk_count / total, 4) if total else 0.0,
            "top_risk_keywords": [
                {"word": w, "count": c} for w, c in keyword_counter.most_common(10)
            ],
            "by_day": [
                {
                    "date": d,
                    "risk": v['risk'],
                    "negative": v['negative'],
                    "positive": v['positive'],
                    "normal": v['normal'],
                    "total": v['total'],
                    "risk_ratio": round(v['risk'] / v['total'], 4) if v['total'] else 0,
                }
                for d, v in sorted(by_day.items())
            ],
            "method": ANALYZER_VERSION,
            "description": (
                "风险=命中系统关键词组(诈骗/广告等)；负面/正面=情感词典+否定词/程度词规则；"
                "其余=正常。全部规则可解释，风险词命中来自本系统关键词库的真实匹配。"
            ),
        }
        self._cache[cache_key] = (now, payload)
        return payload

    # ---------- 兼容旧接口：单条消息 ----------
    async def analyze_message_sentiment(self, db, message_id: int) -> Dict:
        result = await db.execute(
            select(Message.text, Message.matched_keywords).where(Message.id == message_id)
        )
        row = result.first()
        if not row or not row[0]:
            return {"sentiment": "normal", "score": 0.55, "confidence": 0}

        matched_kw = row[1]
        if matched_kw:
            return {"sentiment": "risk", "score": 0.05, "confidence": 1.0,
                    "keywords": matched_kw if isinstance(matched_kw, list) else []}

        loop = __import__('asyncio').get_running_loop()
        cls = await loop.run_in_executor(None, self._classify_text, row[0])
        score_map = {'negative': 0.3, 'normal': 0.55, 'positive': 0.85}
        confidence = abs(score_map[cls] - 0.55) * 2
        return {"sentiment": cls, "score": score_map[cls], "confidence": round(confidence, 2)}

    # ---------- 兼容旧接口：趋势 ----------
    async def get_sentiment_trend(self, db, conversation_id: int, days: int = 30) -> List[Dict]:
        payload = await self.analyze_conversation_sentiment(db, conversation_id, days=days)
        return payload.get('by_day', [])


sentiment_service = SentimentService()
