"""数据分析和高级功能 API"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.api.deps import get_db
from app.services.wordcloud_service import wordcloud_service
from app.services.sentiment_service import sentiment_service
from app.services.report_service import report_service

router = APIRouter(prefix="/analysis", tags=["数据分析"])


@router.get("/wordcloud/image")
async def get_wordcloud(
    conversation_id: Optional[int] = Query(None),
    sender_id: Optional[int] = Query(None),
    days: int = Query(7, ge=1, le=365),
    width: int = Query(800, ge=400, le=2000),
    height: int = Query(400, ge=200, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """获取词云图片 (base64)"""
    try:
        image_base64 = await wordcloud_service.generate_wordcloud(
            db, conversation_id, sender_id, days, width, height
        )

        if image_base64 is None:
            raise HTTPException(
                status_code=501,
                detail="词云功能未启用，请安装 wordcloud 和 jieba: pip install wordcloud jieba matplotlib"
            )

        return {"image": image_base64}
    except Exception as e:
        logger.error(f"生成词云失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wordcloud/words")
async def get_top_words(
    conversation_id: Optional[int] = Query(None),
    sender_id: Optional[int] = Query(None),
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(50, ge=10, le=500),
    db: AsyncSession = Depends(get_db)
):
    """获取高频词列表"""
    try:
        words = await wordcloud_service.get_top_words(
            db, conversation_id, sender_id, days, limit
        )
        return {"words": words}
    except Exception as e:
        logger.error(f"获取高频词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wordcloud/trend")
async def get_keyword_trend(
    keyword: str = Query(..., min_length=1),
    days: int = Query(30, ge=1, le=365),
    interval: str = Query("day", regex="^(hour|day|week)$"),
    db: AsyncSession = Depends(get_db)
):
    """获取关键词出现趋势"""
    try:
        trend = await wordcloud_service.get_keyword_trend(
            db, keyword, days, interval
        )
        return {"trend": trend}
    except Exception as e:
        logger.error(f"获取关键词趋势失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment/message/{message_id}")
async def analyze_message_sentiment(
    message_id: int,
    db: AsyncSession = Depends(get_db)
):
    """分析单条消息的情感"""
    try:
        result = await sentiment_service.analyze_message_sentiment(db, message_id)
        return result
    except Exception as e:
        logger.error(f"情感分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment/conversation/{conversation_id}")
async def analyze_conversation_sentiment(
    conversation_id: int,
    days: int = Query(7, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """分析会话的整体情感倾向"""
    try:
        result = await sentiment_service.analyze_conversation_sentiment(
            db, conversation_id, days
        )
        return result
    except Exception as e:
        logger.error(f"会话情感分析失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sentiment/trend/{conversation_id}")
async def get_sentiment_trend(
    conversation_id: int,
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db)
):
    """获取情感趋势"""
    try:
        trend = await sentiment_service.get_sentiment_trend(
            db, conversation_id, days
        )
        return {"trend": trend}
    except Exception as e:
        logger.error(f"获取情感趋势失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/daily")
async def get_daily_report(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db)
):
    """获取日报数据"""
    from datetime import datetime

    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    try:
        report = await report_service.generate_daily_report(db, target_date)
        return report
    except Exception as e:
        logger.error(f"生成日报失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/weekly")
async def get_weekly_report(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db)
):
    """获取周报数据"""
    from datetime import datetime

    target_start = None
    if start_date:
        try:
            target_start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，应为 YYYY-MM-DD")

    try:
        report = await report_service.generate_weekly_report(db, target_start)
        return report
    except Exception as e:
        logger.error(f"生成周报失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/pdf/daily")
async def download_daily_report_pdf(
    date: Optional[str] = Query(None, description="日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db)
):
    """下载日报 PDF"""
    from datetime import datetime

    target_date = None
    if date:
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")

    try:
        pdf_bytes = await report_service.generate_pdf_report(db, "daily", target_date)

        if pdf_bytes is None:
            raise HTTPException(
                status_code=501,
                detail="PDF 功能未启用，请安装 reportlab: pip install reportlab"
            )

        report_date = target_date.strftime("%Y-%m-%d") if target_date else datetime.now().strftime("%Y-%m-%d")

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=daily_report_{report_date}.pdf"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成 PDF 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/pdf/weekly")
async def download_weekly_report_pdf(
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db)
):
    """下载周报 PDF"""
    from datetime import datetime

    target_start = None
    if start_date:
        try:
            target_start = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误")

    try:
        pdf_bytes = await report_service.generate_pdf_report(db, "weekly", target_start)

        if pdf_bytes is None:
            raise HTTPException(
                status_code=501,
                detail="PDF 功能未启用，请安装 reportlab: pip install reportlab"
            )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": "attachment; filename=weekly_report.pdf"
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成 PDF 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
