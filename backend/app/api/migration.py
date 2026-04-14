"""数据迁移 API - 一键导出/导入系统所有数据"""
import asyncio
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, UploadFile, File
from fastapi.responses import FileResponse
from loguru import logger

from app.core.config import settings

router = APIRouter(prefix="/migration", tags=["数据迁移"])

# 迁移状态（内存中，简单实现）
_migration_state = {
    "status": "idle",  # idle | exporting | importing
    "progress": "",
    "started_at": None,
    "result": None,
}

BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent  # backend/
PROJECT_ROOT = BASE_DIR.parent
SESSIONS_DIR = BASE_DIR / "sessions"
ENV_FILE = BASE_DIR / ".env"

# 合并导入时保留的配置项（不覆盖）
_KEEP_ENV_KEYS = {
    "MYSQL_HOST", "MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE",
    "DATABASE_TYPE", "HOST", "PORT", "DEBUG", "SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES",
}


def _get_mysql_cmd(db_name: Optional[str] = None):
    """构建mysql/mysqldump命令基础参数"""
    cmd = ["mysql"]
    if settings.MYSQL_HOST:
        cmd += ["-h", settings.MYSQL_HOST]
    if settings.MYSQL_PORT:
        cmd += ["-P", str(settings.MYSQL_PORT)]
    if settings.MYSQL_USER:
        cmd += ["-u", settings.MYSQL_USER]
    if settings.MYSQL_PASSWORD:
        cmd += ["-p" + settings.MYSQL_PASSWORD]
    if db_name:
        cmd.append(db_name)
    return cmd


async def _do_export():
    """后台执行导出"""
    try:
        _migration_state["progress"] = "准备导出..."
        tmpdir = tempfile.mkdtemp(prefix="tg_migration_")
        export_file = os.path.join(tmpdir, "export.sql.gz")
        manifest = {"exported_at": datetime.now().isoformat(), "version": "2.0"}

        # 1. 数据库 dump
        _migration_state["progress"] = "正在导出数据库..."
        dump_cmd = ["mysqldump"]
        if settings.MYSQL_HOST:
            dump_cmd += ["-h", settings.MYSQL_HOST]
        if settings.MYSQL_PORT:
            dump_cmd += ["-P", str(settings.MYSQL_PORT)]
        if settings.MYSQL_USER:
            dump_cmd += ["-u", settings.MYSQL_USER]
        if settings.MYSQL_PASSWORD:
            dump_cmd += ["-p" + settings.MYSQL_PASSWORD]
        dump_cmd += [settings.MYSQL_DATABASE, "--single-transaction", "--routines"]

        proc = await asyncio.create_subprocess_exec(
            *dump_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"mysqldump 失败: {stderr.decode()}")

        with open(export_file, "wb") as f:
            # gzip 压缩
            p_gz = await asyncio.create_subprocess_exec(
                "gzip", "-c", stdin=asyncio.subprocess.PIPE, stdout=f
            )
            await p_gz.communicate(stdout)

        manifest["db_size"] = os.path.getsize(export_file)

        # 2. .env 配置
        _migration_state["progress"] = "正在导出配置..."
        if ENV_FILE.exists():
            shutil.copy2(ENV_FILE, os.path.join(tmpdir, ".env"))
            manifest["has_env"] = True

        # 3. Session 文件
        _migration_state["progress"] = "正在导出 Telegram 会话..."
        if SESSIONS_DIR.exists():
            sessions_copy = os.path.join(tmpdir, "sessions")
            shutil.copytree(SESSIONS_DIR, sessions_copy)
            manifest["session_files"] = [
                f for f in os.listdir(sessions_copy)
                if not f.startswith(".")
            ]

        # 4. 关键数据 JSON 备份
        _migration_state["progress"] = "正在导出关键数据..."
        from app.core.database import AsyncSessionLocal
        from sqlalchemy import text

        async with AsyncSessionLocal() as db:
            tables = ["keywords", "keyword_groups", "alert_rules"]
            json_data = {}
            for table in tables:
                try:
                    result = await db.execute(text(f"SELECT * FROM {table}"))
                    rows = result.mappings().all()
                    json_data[table] = [dict(r) for r in rows]
                except Exception:
                    pass
            if json_data:
                json_path = os.path.join(tmpdir, "data_backup.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, ensure_ascii=False, default=str)
                manifest["data_tables"] = list(json_data.keys())

        # 保存 manifest
        with open(os.path.join(tmpdir, "manifest.json"), "w") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 打包
        _migration_state["progress"] = "正在打包..."
        archive = os.path.join(tmpdir, "tg_monitor_export.tar.gz")
        with tarfile.open(archive, "w:gz") as tar:
            for name in os.listdir(tmpdir):
                if name != "tg_monitor_export.tar.gz":
                    tar.add(os.path.join(tmpdir, name), arcname=name)

        # 移动到固定路径供下载
        download_dir = BASE_DIR / "exports"
        download_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_path = download_dir / f"tg_monitor_export_{ts}.tar.gz"
        shutil.move(archive, final_path)

        _migration_state.update({
            "status": "idle",
            "progress": "导出完成",
            "result": {"file": str(final_path), "size": os.path.getsize(final_path), "manifest": manifest},
        })
        logger.info(f"数据导出完成: {final_path}")

    except Exception as e:
        logger.error(f"导出失败: {e}")
        _migration_state.update({"status": "idle", "progress": f"导出失败: {e}", "result": {"error": str(e)}})


async def _do_import(file_path: str):
    """后台执行导入"""
    try:
        _migration_state["progress"] = "正在解压..."
        tmpdir = tempfile.mkdtemp(prefix="tg_import_")
        with tarfile.open(file_path, "r:gz") as tar:
            # 安全提取：检查路径遍历攻击（Zip Slip）
            for member in tar.getmembers():
                member_path = os.path.normpath(os.path.join(tmpdir, member.name))
                if not member_path.startswith(os.path.normpath(tmpdir) + os.sep) and member_path != os.path.normpath(tmpdir):
                    raise RuntimeError(f"检测到不安全的 tar 成员路径: {member.name}")
            tar.extractall(tmpdir)

        stats = {"tables_imported": 0, "sessions_restored": 0, "env_merged": False}

        # 1. 读取 manifest
        manifest_path = os.path.join(tmpdir, "manifest.json")
        manifest = {}
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)

        # 2. 导入数据库（INSERT IGNORE 模式）
        sql_gz = os.path.join(tmpdir, "export.sql.gz")
        if os.path.exists(sql_gz):
            _migration_state["progress"] = "正在导入数据库..."
            # 解压
            proc = await asyncio.create_subprocess_exec(
                "gzip", "-dc", sql_gz,
                stdout=asyncio.subprocess.PIPE,
            )
            sql_content, _ = await proc.communicate()

            # 替换为 INSERT IGNORE
            sql_text = sql_content.decode("utf-8", errors="replace")
            sql_text = sql_text.replace("INSERT INTO ", "INSERT IGNORE INTO ")

            proc = await asyncio.create_subprocess_exec(
                *_get_mysql_cmd(settings.MYSQL_DATABASE),
                stdin=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate(sql_text.encode())
            if proc.returncode != 0:
                logger.warning(f"数据库导入有警告: {stderr.decode()}")
            stats["tables_imported"] = manifest.get("data_tables", len(manifest.get("session_files", [])))

        # 3. JSON 数据备份导入
        json_backup = os.path.join(tmpdir, "data_backup.json")
        if os.path.exists(json_backup):
            _migration_state["progress"] = "正在导入关键数据..."
            with open(json_backup, "r", encoding="utf-8") as f:
                json_data = json.load(f)

            from app.core.database import AsyncSessionLocal
            from sqlalchemy import text

            async with AsyncSessionLocal() as db:
                for table, rows in json_data.items():
                    if not rows:
                        continue
                    # 验证表名只包含安全字符，防止 SQL 注入
                    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', table):
                        logger.warning(f"跳过不安全的表名: {table}")
                        continue
                    for row in rows:
                        columns = list(row.keys())
                        # 验证列名只包含安全字符
                        if not all(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col) for col in columns):
                            logger.warning(f"跳过包含不安全列名的行: {table}")
                            continue
                        placeholders = [f":{col}" for col in columns]
                        sql = f"INSERT IGNORE INTO {table} ({','.join(columns)}) VALUES ({','.join(placeholders)})"
                        try:
                            await db.execute(text(sql), row)
                        except Exception as e:
                            logger.warning(f"导入 {table} 行失败: {e}")
                await db.commit()
                stats["tables_imported"] += 1

        # 4. 恢复 session 文件
        import_dir = os.path.join(tmpdir, "sessions")
        if os.path.isdir(import_dir):
            _migration_state["progress"] = "正在恢复 Telegram 会话..."
            SESSIONS_DIR.mkdir(exist_ok=True)
            for f in os.listdir(import_dir):
                if not f.startswith("."):
                    shutil.copy2(os.path.join(import_dir, f), SESSIONS_DIR / f)
                    stats["sessions_restored"] += 1

        # 5. 合并 .env
        import_env = os.path.join(tmpdir, ".env")
        if os.path.exists(import_env):
            _migration_state["progress"] = "正在合并配置..."
            env_lines = {}
            with open(import_env) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        env_lines[k.strip()] = v.strip()

            if ENV_FILE.exists():
                with open(ENV_FILE) as f:
                    existing = f.readlines()
                new_lines = []
                updated_keys = set()
                for line in existing:
                    stripped = line.strip()
                    if "=" in stripped and not stripped.startswith("#"):
                        k = stripped.split("=", 1)[0].strip()
                        if k in _KEEP_ENV_KEYS:
                            new_lines.append(line)
                            updated_keys.add(k)
                        elif k in env_lines:
                            new_lines.append(f"{k}={env_lines[k]}\n")
                            updated_keys.add(k)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)
                # 追加新配置
                for k, v in env_lines.items():
                    if k not in updated_keys and k not in _KEEP_ENV_KEYS:
                        new_lines.append(f"{k}={v}\n")
                with open(ENV_FILE, "w") as f:
                    f.writelines(new_lines)
            stats["env_merged"] = True

        # 清理
        shutil.rmtree(tmpdir, ignore_errors=True)
        os.remove(file_path)

        _migration_state.update({
            "status": "idle",
            "progress": "导入完成",
            "result": {"stats": stats, "manifest": manifest},
        })
        logger.info(f"数据导入完成: {stats}")

    except Exception as e:
        logger.error(f"导入失败: {e}")
        _migration_state.update({"status": "idle", "progress": f"导入失败: {e}", "result": {"error": str(e)}})


@router.post("/export")
async def export_data(background_tasks: BackgroundTasks):
    """一键导出所有数据"""
    if _migration_state["status"] != "idle":
        return {"error": True, "message": "已有任务进行中，请稍候", "status": _migration_state}

    _migration_state.update({"status": "exporting", "progress": "开始导出...", "started_at": datetime.now().isoformat(), "result": None})
    background_tasks.add_task(_do_export)
    return {"success": True, "message": "导出任务已开始，请通过 /status 接口查看进度"}


@router.get("/export/download")
async def download_export():
    """下载最新的导出文件"""
    download_dir = BASE_DIR / "exports"
    if not download_dir.exists():
        return {"error": True, "message": "暂无可下载的导出文件"}

    files = sorted(download_dir.glob("tg_monitor_export_*.tar.gz"), reverse=True)
    if not files:
        return {"error": True, "message": "暂无可下载的导出文件"}

    latest = files[0]
    return FileResponse(
        path=str(latest),
        filename=latest.name,
        media_type="application/gzip",
    )


@router.post("/import")
async def import_data(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """一键导入数据"""
    if _migration_state["status"] != "idle":
        return {"error": True, "message": "已有任务进行中，请稍候", "status": _migration_state}

    # 保存上传文件
    tmpdir = tempfile.mkdtemp(prefix="tg_import_upload_")
    file_path = os.path.join(tmpdir, file.filename or "import.tar.gz")
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # 验证是否为tar.gz
    if not tarfile.is_tarfile(file_path):
        os.remove(file_path)
        return {"error": True, "message": "无效的导出文件，请上传 .tar.gz 格式"}

    _migration_state.update({"status": "importing", "progress": "开始导入...", "started_at": datetime.now().isoformat(), "result": None})
    background_tasks.add_task(_do_import, file_path)
    return {"success": True, "message": "导入任务已开始，请通过 /status 接口查看进度"}


@router.get("/status")
async def migration_status():
    """查询迁移状态"""
    return _migration_state
