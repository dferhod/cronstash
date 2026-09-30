from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Job, Server, BackupLog, NotificationConfig, User
from app.schemas.schemas import JobCreate, JobUpdate, JobOut, BackupLogOut
from app.api.deps import get_current_user
from app.services.crontab import sync_system_crontab
from app.services.executor import run_backup_for_job
from app.services.gfs import apply_gfs_purge
from app.services.notifications import dispatch_notifications_for_log

router = APIRouter(prefix="/jobs", tags=["Tâches de sauvegarde"])


def calculate_next_run(cron_expr: str) -> Optional[datetime]:
    """Calculate next execution timestamp using croniter."""
    try:
        from croniter import croniter
        now = datetime.now(timezone.utc)
        iter_cron = croniter(cron_expr, now)
        return iter_cron.get_next(datetime)
    except Exception:
        return None


def serialize_job(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        name=job.name,
        server_id=job.server_id,
        server_name=job.server.name if job.server else None,
        server_type=job.server.server_type if job.server else None,
        database_name=job.database_name,
        cron_expression=job.cron_expression,
        is_active=job.is_active,
        retention_daily=job.retention_daily,
        retention_weekly=job.retention_weekly,
        retention_monthly=job.retention_monthly,
        last_run_at=job.last_run_at,
        next_run_at=job.next_run_at,
        created_at=job.created_at,
        updated_at=job.updated_at
    )


@router.get("", response_model=List[JobOut])
async def list_jobs(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all scheduled backup jobs."""
    result = await db.execute(select(Job).order_by(Job.name))
    jobs = result.scalars().all()
    return [serialize_job(j) for j in jobs]


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    payload: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Create a new backup job and update system crontab."""
    server = await db.get(Server, payload.server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serveur spécifié introuvable")

    # Validate cron expression
    next_dt = calculate_next_run(payload.cron_expression)
    if not next_dt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Expression Cron invalide: '{payload.cron_expression}'"
        )

    job = Job(
        name=payload.name,
        server_id=payload.server_id,
        database_name=payload.database_name,
        cron_expression=payload.cron_expression,
        is_active=payload.is_active,
        retention_daily=payload.retention_daily,
        retention_weekly=payload.retention_weekly,
        retention_monthly=payload.retention_monthly,
        next_run_at=next_dt
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Sync crontab
    all_jobs = (await db.execute(select(Job))).scalars().all()
    sync_system_crontab(list(all_jobs))

    return serialize_job(job)


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details for a specific backup job."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable")
    return serialize_job(job)


@router.put("/{job_id}", response_model=JobOut)
async def update_job(
    job_id: int,
    payload: JobUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update job settings and refresh crontab."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable")

    if payload.server_id is not None and payload.server_id != job.server_id:
        server = await db.get(Server, payload.server_id)
        if not server:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nouveau serveur introuvable")
        job.server_id = payload.server_id

    if payload.cron_expression is not None:
        next_dt = calculate_next_run(payload.cron_expression)
        if not next_dt:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expression Cron invalide")
        job.cron_expression = payload.cron_expression
        job.next_run_at = next_dt

    if payload.name is not None:
        job.name = payload.name
    if payload.database_name is not None:
        job.database_name = payload.database_name
    if payload.is_active is not None:
        job.is_active = payload.is_active
    if payload.retention_daily is not None:
        job.retention_daily = payload.retention_daily
    if payload.retention_weekly is not None:
        job.retention_weekly = payload.retention_weekly
    if payload.retention_monthly is not None:
        job.retention_monthly = payload.retention_monthly

    await db.commit()
    await db.refresh(job)

    # Sync crontab
    all_jobs = (await db.execute(select(Job))).scalars().all()
    sync_system_crontab(list(all_jobs))

    return serialize_job(job)


@router.delete("/{job_id}")
async def delete_job(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a backup job and update system crontab."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable")

    await db.delete(job)
    await db.commit()

    # Sync crontab
    all_jobs = (await db.execute(select(Job))).scalars().all()
    sync_system_crontab(list(all_jobs))

    return {"message": f"Tâche '{job.name}' supprimée avec succès"}


@router.patch("/{job_id}/toggle", response_model=JobOut)
async def toggle_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Toggle a job active/inactive status and refresh crontab."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable")

    job.is_active = not job.is_active
    await db.commit()
    await db.refresh(job)

    # Sync crontab
    all_jobs = (await db.execute(select(Job))).scalars().all()
    sync_system_crontab(list(all_jobs))

    return serialize_job(job)


@router.post("/{job_id}/run-now", response_model=BackupLogOut)
async def run_job_now(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Trigger immediate backup run for a job, apply GFS retention, and notify channels."""
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable")

    server = job.server
    if not server:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Serveur associé introuvable")

    # Log entry
    now = datetime.now(timezone.utc)
    log_entry = BackupLog(
        job_id=job.id,
        job_name=job.name,
        server_name=server.name,
        server_type=server.server_type,
        database_name=job.database_name,
        status="running",
        started_at=now
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)

    # Run backup execution
    backup_root = settings.effective_backup_path
    success, file_path, file_size, duration, err_msg = await run_backup_for_job(
        server=server,
        job=job,
        backup_root=backup_root
    )

    log_entry.finished_at = datetime.now(timezone.utc)
    log_entry.duration_seconds = duration

    if success:
        log_entry.status = "success"
        log_entry.file_path = str(file_path)
        log_entry.file_size_bytes = file_size
        log_entry.error_message = None
        job.last_run_at = log_entry.finished_at

        # Recalculate next run
        job.next_run_at = calculate_next_run(job.cron_expression)

        # Apply GFS Retention Purge
        parent_dir = file_path.parent
        gfs_result = apply_gfs_purge(
            target_dir=parent_dir,
            database_name=job.database_name,
            n1_daily=job.retention_daily,
            n2_weekly=job.retention_weekly,
            n3_monthly=job.retention_monthly
        )
        tiers_map = gfs_result.get("tiers_map", {})
        current_tiers = tiers_map.get(file_path.name, ["daily"])
        log_entry.gfs_tier = ", ".join(current_tiers) if current_tiers else "daily"
    else:
        log_entry.status = "failed"
        log_entry.error_message = err_msg

    # Send notifications
    notif_stmt = select(NotificationConfig).limit(1)
    notif_config = (await db.execute(notif_stmt)).scalar_one_or_none()
    if notif_config:
        try:
            await dispatch_notifications_for_log(notif_config, log_entry)
        except Exception:
            pass

    await db.commit()
    await db.refresh(log_entry)

    return BackupLogOut.model_validate(log_entry)
