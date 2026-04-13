"""系统设置管理 API"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from loguru import logger
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
import json
from datetime import datetime

from app.core.config import settings
from app.api.deps import get_db
from app.models.keyword import KeywordGroup, Keyword
from app.models.notification_config import NotificationConfig
from app.models.settings import Settings

router = APIRouter(prefix="/settings", tags=["settings"])


class SettingsResponse(BaseModel):
    """系统设置响应"""
    # 数据采集设置
    default_history_days: int = Field(default=7, description="默认历史回溯天数")
    default_message_limit: int = Field(default=1000, description="默认历史消息限制")
    batch_size: int = Field(default=100, description="批量处理大小")
    enable_realtime_monitoring: bool = Field(default=True, description="启用实时监控")

    # 通知设置
    enable_browser_notifications: bool = Field(default=True, description="浏览器通知")
    enable_sound_alerts: bool = Field(default=True, description="声音提示")
    minimum_alert_level: str = Field(default="low", description="最低告警级别")

    # 代理设置
    http_proxy: Optional[str] = Field(default=None, description="HTTP 代理")
    socks5_proxy: Optional[str] = Field(default=None, description="SOCKS5 代理")

    # 安全设置
    data_retention_days: int = Field(default=30, description="数据保留天数")
    auto_cleanup_expired_data: bool = Field(default=True, description="自动清理过期数据")


class SettingsUpdate(BaseModel):
    """系统设置更新"""
    # 数据采集设置
    default_history_days: Optional[int] = Field(None, ge=1, le=365, description="默认历史回溯天数")
    default_message_limit: Optional[int] = Field(None, ge=1, le=100000, description="默认历史消息限制")
    batch_size: Optional[int] = Field(None, ge=1, le=1000, description="批量处理大小")
    enable_realtime_monitoring: Optional[bool] = Field(None, description="启用实时监控")

    # 通知设置
    enable_browser_notifications: Optional[bool] = Field(None, description="浏览器通知")
    enable_sound_alerts: Optional[bool] = Field(None, description="声音提示")
    minimum_alert_level: Optional[str] = Field(None, description="最低告警级别")

    # 代理设置
    http_proxy: Optional[str] = Field(None, description="HTTP 代理")
    socks5_proxy: Optional[str] = Field(None, description="SOCKS5 代理")

    # 安全设置
    data_retention_days: Optional[int] = Field(None, ge=1, le=365, description="数据保留天数")
    auto_cleanup_expired_data: Optional[bool] = Field(None, description="自动清理过期数据")


# 全局设置存储（在实际应用中应该存储在数据库或配置文件中）
_global_settings = SettingsResponse()


@router.get("", response_model=SettingsResponse)
async def get_settings():
    """获取系统设置"""
    logger.debug(f"Getting settings: {_global_settings}")
    return _global_settings


@router.put("", response_model=SettingsResponse)
async def update_settings(update_data: SettingsUpdate):
    """更新系统设置"""
    logger.debug(f"Updating settings with data: {update_data}")

    # 获取所有非 None 的字段进行更新
    update_dict = update_data.model_dump(exclude_none=True)

    if not update_dict:
        logger.warning("No settings to update")
        raise HTTPException(status_code=400, detail="没有要更新的设置")

    for key, value in update_dict.items():
        if hasattr(_global_settings, key):
            old_value = getattr(_global_settings, key)
            setattr(_global_settings, key, value)
            logger.debug(f"Updated {key}: {old_value} -> {value}")
        else:
            logger.warning(f"Unknown setting key: {key}")

    logger.info(f"Settings updated: {update_dict}")
    return _global_settings


@router.post("/reset", response_model=SettingsResponse)
async def reset_settings():
    """重置系统设置为默认值"""
    global _global_settings
    _global_settings = SettingsResponse()
    logger.info("Settings reset to defaults")
    return _global_settings


# ==================== 导入导出功能 ====================

class ExportData(BaseModel):
    """导出数据结构"""
    version: str = "1.0"
    export_time: str
    system_settings: Dict[str, Any]
    keyword_groups: List[Dict[str, Any]] = []
    notification_configs: List[Dict[str, Any]] = []


@router.get("/export")
async def export_all_data(db: AsyncSession = Depends(get_db)) -> ExportData:
    """导出所有配置数据（系统设置、关键词、通知配置）"""
    try:
        # 导出系统设置
        system_settings = _global_settings.model_dump()

        # 导出关键词组
        keyword_groups_data = []
        result = await db.execute(select(KeywordGroup))
        keyword_groups = result.scalars().all()

        for kg in keyword_groups:
            # 获取关键词组下的所有关键词
            kw_result = await db.execute(
                select(Keyword).where(Keyword.group_id == kg.id)
            )
            keywords = kw_result.scalars().all()

            keyword_groups_data.append({
                "id": kg.id,
                "name": kg.name,
                "description": kg.description,
                "match_type": kg.match_type,
                "case_sensitive": kg.case_sensitive,
                "alert_level": kg.alert_level,
                "is_active": kg.is_active,
                "keywords": [
                    {
                        "word": kw.word,
                        "match_type": kw.match_type,
                        "case_sensitive": kw.case_sensitive,
                        "alert_level": kw.alert_level,
                    }
                    for kw in keywords
                ]
            })

        # 导出通知配置
        notification_configs_data = []
        result = await db.execute(select(NotificationConfig))
        configs = result.scalars().all()

        for config in configs:
            # 不导出敏感信息（密码、token等）
            safe_config = {
                "id": config.id,
                "name": config.name,
                "type": config.notification_type,
                "is_active": config.is_active,
                "alert_levels": [config.min_alert_level] if config.min_alert_level else [],
            }
            # 保留配置结构但用占位符替换敏感信息
            notification_configs_data.append(safe_config)

        export_data = ExportData(
            version="1.0",
            export_time=datetime.now().isoformat(),
            system_settings=system_settings,
            keyword_groups=keyword_groups_data,
            notification_configs=notification_configs_data,
        )

        logger.info(f"Exported data: {len(keyword_groups_data)} keyword groups, {len(notification_configs_data)} notification configs")
        return export_data

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.post("/import")
async def import_all_data(
    data: ExportData,
    db: AsyncSession = Depends(get_db)
):
    """导入所有配置数据"""
    try:
        import_results = {
            "system_settings": {"success": False, "message": ""},
            "keyword_groups": {"imported": 0, "skipped": 0, "errors": []},
            "notification_configs": {"imported": 0, "skipped": 0, "errors": []},
        }

        # 导入系统设置
        try:
            global _global_settings
            for key, value in data.system_settings.items():
                if hasattr(_global_settings, key):
                    setattr(_global_settings, key, value)
            import_results["system_settings"] = {"success": True, "message": "系统设置已导入"}
            logger.info("System settings imported successfully")
        except Exception as e:
            import_results["system_settings"] = {"success": False, "message": str(e)}
            logger.error(f"Failed to import system settings: {e}")

        # 导入关键词组
        for kg_data in data.keyword_groups:
            try:
                # 检查是否已存在同名关键词组
                existing = await db.execute(
                    select(KeywordGroup).where(KeywordGroup.name == kg_data["name"])
                )
                existing_group = existing.scalar_one_or_none()

                if existing_group:
                    import_results["keyword_groups"]["skipped"] += 1
                    continue

                # 创建新的关键词组
                new_group = KeywordGroup(
                    name=kg_data["name"],
                    description=kg_data.get("description"),
                    match_type=kg_data.get("match_type", "contains"),
                    case_sensitive=kg_data.get("case_sensitive", False),
                    alert_level=kg_data.get("alert_level", "medium"),
                    is_active=kg_data.get("is_active", True),
                )
                db.add(new_group)
                await db.flush()  # 获取 ID

                # 创建关键词
                for kw_data in kg_data.get("keywords", []):
                    keyword = Keyword(
                        group_id=new_group.id,
                        word=kw_data["word"],
                        match_type=kw_data.get("match_type", kg_data.get("match_type", "contains")),
                        case_sensitive=kw_data.get("case_sensitive", kg_data.get("case_sensitive", False)),
                        alert_level=kw_data.get("alert_level", kg_data.get("alert_level", "medium")),
                    )
                    db.add(keyword)

                import_results["keyword_groups"]["imported"] += 1

            except Exception as e:
                import_results["keyword_groups"]["errors"].append(f"{kg_data.get('name', 'Unknown')}: {str(e)}")
                logger.error(f"Failed to import keyword group {kg_data.get('name')}: {e}")

        # 导入通知配置（仅导入结构，不包含敏感信息）
        for config_data in data.notification_configs:
            try:
                # 检查是否已存在同名配置
                existing = await db.execute(
                    select(NotificationConfig).where(NotificationConfig.name == config_data["name"])
                )
                existing_config = existing.scalar_one_or_none()

                if existing_config:
                    import_results["notification_configs"]["skipped"] += 1
                    continue

                # 创建新的通知配置（未配置状态）
                new_config = NotificationConfig(
                    name=config_data["name"],
                    notification_type=config_data["type"],
                    is_active=False,  # 导入的配置默认禁用，需要重新配置
                    min_alert_level=(config_data.get("alert_levels") or ["high"])[0] if config_data.get("alert_levels") else None,
                )
                db.add(new_config)
                import_results["notification_configs"]["imported"] += 1

            except Exception as e:
                import_results["notification_configs"]["errors"].append(f"{config_data.get('name', 'Unknown')}: {str(e)}")
                logger.error(f"Failed to import notification config {config_data.get('name')}: {e}")

        await db.commit()

        logger.info(f"Import completed: {import_results}")
        return {
            "success": True,
            "message": "导入完成",
            "details": import_results,
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Import failed: {e}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


@router.get("/export/keywords")
async def export_keywords(db: AsyncSession = Depends(get_db)):
    """单独导出关键词配置"""
    try:
        result = await db.execute(select(KeywordGroup))
        keyword_groups = result.scalars().all()

        data = []
        for kg in keyword_groups:
            kw_result = await db.execute(
                select(Keyword).where(Keyword.group_id == kg.id)
            )
            keywords = kw_result.scalars().all()

            data.append({
                "name": kg.name,
                "description": kg.description,
                "match_type": kg.match_type,
                "case_sensitive": kg.case_sensitive,
                "alert_level": kg.alert_level,
                "is_active": kg.is_active,
                "keywords": [kw.word for kw in keywords],
            })

        return {
            "version": "1.0",
            "export_time": datetime.now().isoformat(),
            "data": data,
        }

    except Exception as e:
        logger.error(f"Export keywords failed: {e}")
        raise HTTPException(status_code=500, detail=f"导出失败: {str(e)}")


@router.post("/import/keywords")
async def import_keywords(
    data: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """单独导入关键词配置"""
    try:
        imported = 0
        skipped = 0
        errors = []

        for kg_data in data.get("data", []):
            try:
                # 检查是否已存在
                existing = await db.execute(
                    select(KeywordGroup).where(KeywordGroup.name == kg_data["name"])
                )
                existing_group = existing.scalar_one_or_none()

                if existing_group:
                    # 合并：向已有组添加新关键词
                    target_group_id = existing_group.id
                    merged = True
                else:
                    # 创建新关键词组
                    new_group = KeywordGroup(
                        name=kg_data["name"],
                        description=kg_data.get("description"),
                        match_type=kg_data.get("match_type", "contains"),
                        case_sensitive=kg_data.get("case_sensitive", False),
                        alert_level=kg_data.get("alert_level", "medium"),
                        is_active=kg_data.get("is_active", True),
                    )
                    db.add(new_group)
                    await db.flush()
                    target_group_id = new_group.id
                    merged = False

                # 添加关键词（跳过已存在的）
                added_count = 0
                for word in kg_data.get("keywords", []):
                    word = word.strip()
                    if not word:
                        continue
                    dup = await db.execute(
                        select(Keyword).where(
                            Keyword.group_id == target_group_id,
                            Keyword.word == word
                        )
                    )
                    if not dup.scalar_one_or_none():
                        keyword = Keyword(
                            group_id=target_group_id,
                            word=word,
                            match_type=kg_data.get("match_type", "contains"),
                            case_sensitive=kg_data.get("case_sensitive", False),
                            alert_level=kg_data.get("alert_level", "medium"),
                        )
                        db.add(keyword)
                        added_count += 1

                if merged:
                    skipped += 1  # 组已存在（但关键词已合并）
                else:
                    imported += 1

            except Exception as e:
                errors.append(f"{kg_data.get('name', 'Unknown')}: {str(e)}")

        await db.commit()

        return {
            "success": True,
            "imported": imported,
            "skipped": skipped,
            "errors": errors,
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"Import keywords failed: {e}")
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")


# ==================== 数据清理功能 ====================

from pydantic import Field


class CleanupStatsResponse(BaseModel):
    """清理统计响应"""
    retention_days: int = Field(description="数据保留天数")
    cutoff_time: str = Field(description="截止时间")
    expired: Dict[str, Any] = Field(description="过期数据统计")
    total: Dict[str, Any] = Field(description="总数据统计")
    database_size_bytes: int = Field(description="数据库大小（字节）")
    database_size_mb: float = Field(description="数据库大小（MB）")


class CleanupRequest(BaseModel):
    """清理请求"""
    retention_days: Optional[int] = Field(None, ge=1, le=365, description="保留天数（可选，默认使用系统配置）")
    dry_run: bool = Field(False, description="演练模式，不实际删除")


@router.get("/cleanup/stats", response_model=CleanupStatsResponse)
async def get_cleanup_stats():
    """获取数据清理统计"""
    from app.services.data_cleanup_service import data_cleanup_service

    try:
        stats = await data_cleanup_service.get_cleanup_stats()

        if "error" in stats:
            raise HTTPException(status_code=500, detail=stats["error"])

        return CleanupStatsResponse(**stats)
    except Exception as e:
        logger.error(f"获取清理统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")


@router.post("/cleanup/run")
async def run_cleanup(request: CleanupRequest):
    """手动执行数据清理"""
    from app.services.data_cleanup_service import data_cleanup_service

    try:
        result = await data_cleanup_service.cleanup_all(
            retention_days=request.retention_days,
            dry_run=request.dry_run
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "清理失败")
            )

        # 添加可读的消息
        if request.dry_run:
            result["message"] = f"[演练模式] 将删除 {result.get('total_deleted', 0)} 条过期数据"
        else:
            result["message"] = f"清理完成，删除了 {result.get('total_deleted', 0)} 条过期数据"

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"执行清理失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.post("/cleanup/alerts")
async def cleanup_alerts(request: CleanupRequest):
    """仅清理过期告警"""
    from app.services.data_cleanup_service import data_cleanup_service

    try:
        result = await data_cleanup_service.cleanup_expired_alerts(
            retention_days=request.retention_days,
            dry_run=request.dry_run
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "清理失败")
            )

        if request.dry_run:
            result["message"] = f"[演练模式] 将删除 {result.get('deleted_count', 0)} 条过期告警"
        else:
            result["message"] = f"清理完成，删除了 {result.get('deleted_count', 0)} 条过期告警"

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清理告警失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


@router.post("/cleanup/messages")
async def cleanup_messages(request: CleanupRequest):
    """仅清理过期消息（无告警关联的）"""
    from app.services.data_cleanup_service import data_cleanup_service

    try:
        result = await data_cleanup_service.cleanup_expired_messages(
            retention_days=request.retention_days,
            dry_run=request.dry_run
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("message", "清理失败")
            )

        if request.dry_run:
            result["message"] = f"[演练模式] 将删除 {result.get('deleted_count', 0)} 条过期消息"
        else:
            result["message"] = f"清理完成，删除了 {result.get('deleted_count', 0)} 条过期消息"

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"清理消息失败: {e}")
        raise HTTPException(status_code=500, detail=f"清理失败: {str(e)}")


# ==================== 数据库配置管理（新增） ====================

class SettingItem(BaseModel):
    """单个配置项"""
    key: str
    value: str
    category: Optional[str] = "general"


class SettingsBatchUpdate(BaseModel):
    """批量更新配置"""
    settings: Dict[str, str]


@router.get("/db")
async def get_db_settings(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """获取数据库中的所有配置（可按分类过滤）"""
    try:
        query = select(Settings)
        if category:
            query = query.where(Settings.category == category)

        result = await db.execute(query)
        settings_list = result.scalars().all()

        # 转换为字典格式
        settings_dict = {}
        for setting in settings_list:
            settings_dict[setting.key_name] = {
                "value": setting.value,
                "category": setting.category,
                "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
            }

        return {
            "success": True,
            "settings": settings_dict
        }

    except Exception as e:
        logger.error(f"获取数据库配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


@router.put("/db")
async def update_db_settings(
    data: SettingsBatchUpdate,
    db: AsyncSession = Depends(get_db)
):
    """批量更新数据库配置"""
    try:
        updated_count = 0

        for key, value in data.settings.items():
            # 查找现有配置
            result = await db.execute(
                select(Settings).where(Settings.key_name == key)
            )
            setting = result.scalar_one_or_none()

            if setting:
                # 更新现有配置
                setting.value = value
            else:
                # 创建新配置（自动分类）
                category = "general"
                if any(kw in key.lower() for kw in ["proxy", "node", "subscribe"]):
                    category = "proxy"
                elif any(kw in key.lower() for kw in ["notify", "bot", "alert"]):
                    category = "notification"
                elif any(kw in key.lower() for kw in ["account", "api_id", "api_hash"]):
                    category = "account"

                setting = Settings(
                    key_name=key,
                    value=value,
                    category=category
                )
                db.add(setting)

            updated_count += 1

        await db.commit()
        logger.info(f"批量更新了 {updated_count} 个配置项")

        return {
            "success": True,
            "updated_count": updated_count,
            "message": f"成功更新 {updated_count} 个配置项"
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"批量更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.get("/db/{key}")
async def get_db_setting(
    key: str,
    db: AsyncSession = Depends(get_db)
):
    """获取单个数据库配置"""
    try:
        result = await db.execute(
            select(Settings).where(Settings.key_name == key)
        )
        setting = result.scalar_one_or_none()

        if not setting:
            return {
                "success": False,
                "key": key,
                "value": None,
                "message": "配置项不存在"
            }

        return {
            "success": True,
            "key": setting.key_name,
            "value": setting.value,
            "category": setting.category,
            "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
        }

    except Exception as e:
        logger.error(f"获取配置失败: {key}, 错误: {e}")
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")


class SettingUpdateRequest(BaseModel):
    """单个配置更新请求"""
    value: str = Field(..., description="配置值")
    category: Optional[str] = Field("general", description="配置分类")


@router.put("/db/{key}")
async def update_db_setting(
    key: str,
    request: SettingUpdateRequest,
    db: AsyncSession = Depends(get_db)
):
    """更新单个数据库配置"""
    try:
        # 检查空值
        if not request.value or request.value.strip() == "":
            raise HTTPException(status_code=400, detail="配置值不能为空")

        result = await db.execute(
            select(Settings).where(Settings.key_name == key)
        )
        setting = result.scalar_one_or_none()

        if setting:
            setting.value = request.value
            if request.category:
                setting.category = request.category
        else:
            setting = Settings(
                key_name=key,
                value=request.value,
                category=request.category
            )
            db.add(setting)

        await db.commit()
        logger.info(f"配置已更新: {key} = {request.value}")

        return {
            "success": True,
            "key": key,
            "value": request.value,
            "category": setting.category,
            "message": "配置更新成功"
        }
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"更新配置失败: {key}, 错误: {e}")
        raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")


@router.delete("/db/{key}")
async def delete_db_setting(
    key: str,
    db: AsyncSession = Depends(get_db)
):
    """删除单个数据库配置"""
    try:
        result = await db.execute(
            delete(Settings).where(Settings.key_name == key)
        )

        await db.commit()
        deleted_count = result.rowcount

        if deleted_count == 0:
            return {
                "success": False,
                "message": "配置项不存在"
            }

        logger.info(f"配置已删除: {key}")

        return {
            "success": True,
            "key": key,
            "message": "配置删除成功"
        }

    except Exception as e:
        await db.rollback()
        logger.error(f"删除配置失败: {key}, 错误: {e}")
        raise HTTPException(status_code=500, detail=f"删除失败: {str(e)}")


@router.get("/initialized")
async def check_initialized(db: AsyncSession = Depends(get_db)):
    """检查系统是否已初始化"""
    try:
        result = await db.execute(
            select(Settings).where(Settings.key_name == "initialized")
        )
        setting = result.scalar_one_or_none()

        is_initialized = setting and setting.value == "true"

        return {
            "initialized": is_initialized,
            "value": setting.value if setting else None
        }

    except Exception as e:
        logger.error(f"检查初始化状态失败: {e}")
        # 如果表不存在，返回未初始化
        return {
            "initialized": False,
            "error": str(e)
        }

