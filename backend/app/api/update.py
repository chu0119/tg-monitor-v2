"""系统更新 API"""
import asyncio
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/system", tags=["system"])

# GitHub 配置
GITHUB_REPO = "chu0119/tg-monitor-v2"
GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}"

# 项目根目录（backend 的上级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# 更新锁
_update_lock = asyncio.Lock()
_update_status = {
    "updating": False,
    "progress": "",
    "log": [],
    "success": None,
    "error": None,
}


class UpdateStatusResponse(BaseModel):
    current_version: str
    current_commit: str
    branch: str


class CheckUpdateResponse(BaseModel):
    has_update: bool
    current_version: str
    current_commit: str
    remote_commit: str
    commits_behind: int
    changelog: list[str]


def _get_git_output(args: list[str]) -> str:
    """执行 git 命令并返回输出"""
    result = subprocess.run(
        ["git"] + args,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _get_local_commit() -> str:
    return _get_git_output(["rev-parse", "HEAD"])


def _get_local_branch() -> str:
    try:
        return _get_git_output(["rev-parse", "--abbrev-ref", "HEAD"])
    except RuntimeError:
        return "main"


@router.get("/update-status", response_model=UpdateStatusResponse)
async def get_update_status():
    """获取当前版本信息"""
    try:
        commit = _get_local_commit()
        branch = _get_local_branch()
        return UpdateStatusResponse(
            current_version=settings.VERSION,
            current_commit=commit,
            branch=branch,
        )
    except Exception as e:
        logger.error(f"获取版本信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-update", response_model=CheckUpdateResponse)
async def check_update():
    """检查 GitHub 是否有新版本"""
    try:
        local_commit = _get_local_commit()

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{GITHUB_API}/commits/main",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code != 200:
                raise RuntimeError(f"GitHub API 返回 {resp.status_code}: {resp.text[:200]}")

            commits = resp.json()
            if not commits:
                return CheckUpdateResponse(
                    has_update=False,
                    current_version=settings.VERSION,
                    current_commit=local_commit,
                    remote_commit=local_commit,
                    commits_behind=0,
                    changelog=[],
                )

            remote_commit = commits[0]["sha"]

            # 计算落后几个 commit
            changelog = []
            commits_behind = 0
            for c in commits:
                if c["sha"] == local_commit:
                    break
                commits_behind += 1
                msg = c["commit"]["message"].split("\n")[0]
                changelog.append(f"[{c['sha'][:7]}] {msg}")

            return CheckUpdateResponse(
                has_update=local_commit != remote_commit,
                current_version=settings.VERSION,
                current_commit=local_commit,
                remote_commit=remote_commit,
                commits_behind=commits_behind,
                changelog=changelog,
            )
    except Exception as e:
        logger.error(f"检查更新失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/perform-update")
async def perform_update():
    """执行系统更新"""
    if _update_lock.locked():
        raise HTTPException(status_code=409, detail="更新正在进行中，请勿重复操作")

    async with _update_lock:
        _update_status["updating"] = True
        _update_status["progress"] = "准备更新..."
        _update_status["log"] = []
        _update_status["success"] = None
        _update_status["error"] = None

        def _log(msg: str):
            logger.info(f"[更新] {msg}")
            _update_status["log"].append(msg)
            _update_status["progress"] = msg

        try:
            # 1. 检查本地修改
            _log("检查本地修改...")
            status_out = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if status_out.stdout.strip():
                # 检查是否有未暂存的修改（排除新文件）
                has_staged = subprocess.run(
                    ["git", "diff", "--cached", "--quiet"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                ).returncode != 0
                has_unstaged = subprocess.run(
                    ["git", "diff", "--quiet"],
                    cwd=PROJECT_ROOT,
                    capture_output=True,
                ).returncode != 0

                if has_staged or has_unstaged:
                    _log("发现本地修改，暂存到 stash...")
                    subprocess.run(
                        ["git", "stash", "push", "-m", "auto-update-stash"],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )

            # 记录当前 commit（用于回滚）
            old_commit = _get_git_output(["rev-parse", "HEAD"])
            _log(f"当前版本: {old_commit[:7]}")

            # 2. 备份数据库
            _log("备份数据库...")
            db_backup_path = PROJECT_ROOT / "backups" / f"pre-update-{old_commit[:7]}.sql"
            db_backup_path.parent.mkdir(parents=True, exist_ok=True)

            # 尝试使用 mysqldump 备份
            try:
                from app.core.config import settings as cfg
                if cfg.DB_HOST and cfg.DB_USER:
                    db_name = cfg.DB_NAME or "tg_monitor"
                    dump_cmd = [
                        "mysqldump",
                        f"-h{cfg.DB_HOST}",
                        f"-P{cfg.DB_PORT or 3306}",
                        f"-u{cfg.DB_USER}",
                    ]
                    if cfg.DB_PASSWORD:
                        dump_cmd.append(f"-p{cfg.DB_PASSWORD}")
                    dump_cmd.append(db_name)

                    result = subprocess.run(
                        dump_cmd,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )
                    if result.returncode == 0:
                        db_backup_path.write_text(result.stdout)
                        _log(f"数据库备份成功: {db_backup_path.name}")
                    else:
                        _log(f"数据库备份警告: {result.stderr[:100]}")
                else:
                    _log("跳过数据库备份（未配置数据库）")
            except Exception as e:
                _log(f"数据库备份跳过: {str(e)[:100]}")

            # 3. 拉取代码
            _log("拉取最新代码...")
            pull_result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if pull_result.returncode != 0:
                _log(f"git pull 失败: {pull_result.stderr.strip()}")
                # 回滚
                _log("回滚到更新前版本...")
                subprocess.run(["git", "reset", "--hard", old_commit], cwd=PROJECT_ROOT, capture_output=True, timeout=30)
                raise HTTPException(status_code=500, detail=f"git pull 失败: {pull_result.stderr.strip()}")
            _log(pull_result.stdout.strip() or "代码已是最新")

            new_commit = _get_git_output(["rev-parse", "HEAD"])
            if new_commit == old_commit:
                _log("代码已是最新版本，无需更新依赖")
            else:
                # 4. 安装后端依赖
                _log("安装后端依赖...")
                req_file = PROJECT_ROOT / "backend" / "requirements.txt"
                if req_file.exists():
                    pip_result = subprocess.run(
                        ["pip", "install", "-r", str(req_file), "-q"],
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if pip_result.returncode != 0:
                        _log(f"pip install 警告: {pip_result.stderr[-200:]}")
                    else:
                        _log("后端依赖安装完成")
                else:
                    _log("未找到 requirements.txt，跳过")

                # 5. 安装前端依赖并构建
                frontend_dir = PROJECT_ROOT / "frontend"
                pkg_file = frontend_dir / "package.json"
                if pkg_file.exists():
                    _log("安装前端依赖...")
                    npm_result = subprocess.run(
                        ["npm", "install"],
                        cwd=frontend_dir,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if npm_result.returncode != 0:
                        _log(f"npm install 警告: {npm_result.stderr[-200:]}")
                    else:
                        _log("前端依赖安装完成")

                    # 检查是否有 build 脚本
                    _log("构建前端...")
                    build_result = subprocess.run(
                        ["npm", "run", "build"],
                        cwd=frontend_dir,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    if build_result.returncode != 0:
                        _log(f"前端构建失败: {build_result.stderr[-200:]}")
                        _log("前端构建失败，不影响后端运行")
                    else:
                        _log("前端构建完成")
                else:
                    _log("未找到前端目录，跳过前端构建")

                _log(f"更新成功: {old_commit[:7]} → {new_commit[:7]}")

            # 6. 重启服务
            _log("重启服务...")
            restart_result = subprocess.run(
                ["sudo", "systemctl", "restart", "tg-monitor"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if restart_result.returncode != 0:
                _log(f"systemctl restart 失败（可手动重启）: {restart_result.stderr.strip()}")
            else:
                _log("服务重启命令已执行")

            _update_status["success"] = True
            return {
                "success": True,
                "message": "更新完成，服务正在重启",
                "old_commit": old_commit[:7],
                "new_commit": _get_git_output(["rev-parse", "HEAD"])[:7],
                "log": _update_status["log"],
            }

        except HTTPException:
            _update_status["success"] = False
            _update_status["updating"] = False
            raise
        except Exception as e:
            _log(f"更新失败: {str(e)}")
            _update_status["success"] = False
            _update_status["error"] = str(e)
            _update_status["updating"] = False
            raise HTTPException(status_code=500, detail=f"更新失败: {str(e)}")
        finally:
            _update_status["updating"] = False


@router.get("/update-progress")
async def get_update_progress():
    """获取更新进度（轮询用）"""
    return _update_status
