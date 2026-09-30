import shutil
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Server, Job, BackupLog, User
from app.schemas.schemas import DashboardStatsOut, DiskStats, Last24HoursStats, BackupLogOut
from app.api.deps import get_current_user
from app.services.notifications import format_bytes

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStatsOut)
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve system health, disk metrics in /backup/cronstash, and 24h backup stats."""
    # 1. Disk usage calculation on backup destination
    backup_path = settings.effective_backup_path
    try:
        usage = shutil.disk_usage(backup_path)
        total_b = usage.total
        free_b = usage.free
        used_b = usage.used
        pct = round((used_b / total_b) * 100, 1) if total_b > 0 else 0.0
    except Exception:
        total_b, used_b, free_b, pct = 0, 0, 0, 0.0

    disk_stats = DiskStats(
        total_bytes=total_b,
        used_bytes=used_b,
        free_bytes=free_b,
        used_percent=pct,
        total_formatted=format_bytes(total_b),
        used_formatted=format_bytes(used_b),
        free_formatted=format_bytes(free_b)
    )

    # 2. Total servers & jobs count
    servers_cnt_res = await db.execute(select(func.count(Server.id)))
    total_servers = servers_cnt_res.scalar() or 0

    jobs_cnt_res = await db.execute(select(func.count(Job.id)))
    total_jobs = jobs_cnt_res.scalar() or 0

    active_jobs_cnt_res = await db.execute(select(func.count(Job.id)).where(Job.is_active.is_(True)))
    active_jobs = active_jobs_cnt_res.scalar() or 0

    # 3. Last 24 hours stats
    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    total_24h_res = await db.execute(
        select(func.count(BackupLog.id)).where(BackupLog.started_at >= since_24h)
    )
    total_24h = total_24h_res.scalar() or 0

    success_24h_res = await db.execute(
        select(func.count(BackupLog.id)).where(
            BackupLog.started_at >= since_24h,
            BackupLog.status == "success"
        )
    )
    success_24h = success_24h_res.scalar() or 0

    failed_24h_res = await db.execute(
        select(func.count(BackupLog.id)).where(
            BackupLog.started_at >= since_24h,
            BackupLog.status == "failed"
        )
    )
    failed_24h = failed_24h_res.scalar() or 0

    rate = round((success_24h / total_24h) * 100, 1) if total_24h > 0 else 100.0

    stats_24h = Last24HoursStats(
        total_runs=total_24h,
        success_runs=success_24h,
        failed_runs=failed_24h,
        success_rate=rate
    )

    # 4. Recent 10 logs
    logs_res = await db.execute(
        select(BackupLog).order_by(desc(BackupLog.started_at)).limit(10)
    )
    recent_logs = logs_res.scalars().all()

    return DashboardStatsOut(
        disk=disk_stats,
        total_servers=total_servers,
        total_jobs=total_jobs,
        active_jobs=active_jobs,
        stats_24h=stats_24h,
        recent_logs=[BackupLogOut.model_validate(l) for l in recent_logs]
    )
