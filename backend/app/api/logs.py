from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, delete

from app.core.database import get_db
from app.models.models import BackupLog, User
from app.schemas.schemas import BackupLogOut
from app.api.deps import get_current_user

router = APIRouter(prefix="/logs", tags=["Logs d'exécution"])


@router.get("", response_model=List[BackupLogOut])
async def list_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    server_filter: Optional[str] = Query(None, alias="server"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve filtered and paginated execution logs."""
    query = select(BackupLog)

    if status_filter:
        query = query.where(BackupLog.status == status_filter)
    if server_filter:
        query = query.where(BackupLog.server_name.ilike(f"%{server_filter}%"))

    query = query.order_by(desc(BackupLog.started_at)).limit(limit).offset(offset)
    res = await db.execute(query)
    logs = res.scalars().all()
    return [BackupLogOut.model_validate(l) for l in logs]


@router.delete("/{log_id}")
async def delete_single_log(
    log_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a specific log entry."""
    entry = await db.get(BackupLog, log_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entrée de journal introuvable")

    await db.delete(entry)
    await db.commit()
    return {"message": "Entrée de log supprimée"}


@router.delete("")
async def purge_logs(
    days: int = Query(30, ge=1, le=365, description="Supprimer les logs plus vieux que N jours"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Purge execution logs older than specified number of days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = delete(BackupLog).where(BackupLog.started_at < cutoff)
    result = await db.execute(stmt)
    await db.commit()
    return {"message": f"Logs antérieurs à {days} jours purgés ({result.rowcount} entrées)"}
