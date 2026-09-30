import os
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.models.models import Server, Job, BackupLog, User
from app.schemas.schemas import BackupFileItem, BackupLogOut
from app.api.deps import get_current_user
from app.services.notifications import format_bytes
from app.services.gfs import parse_backup_file
from app.services.executor import run_backup_for_job

router = APIRouter(prefix="/backups", tags=["Sauvegardes"])


class InstantBackupRequest(BaseModel):
    server_id: int
    database_name: str


def sanitize_relative_path(rel_path: str) -> Path:
    """Safeguard against path traversal attacks."""
    clean_parts = [p for p in rel_path.replace("\\", "/").split("/") if p and p != ".."]
    safe_rel = Path(*clean_parts)
    full_path = (settings.effective_backup_path / safe_rel).resolve()
    
    # Must reside inside effective_backup_path
    if not str(full_path).startswith(str(settings.effective_backup_path.resolve())):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chemin de fichier interdit")
    return full_path


@router.get("", response_model=List[BackupFileItem])
async def list_backup_files(
    current_user: User = Depends(get_current_user)
):
    """Recursively list all physical backup files in /backup/cronstash."""
    backup_root = settings.effective_backup_path
    files_list: List[BackupFileItem] = []

    for engine_type in ["pgsql", "rdf4j"]:
        engine_dir = backup_root / engine_type
        if not engine_dir.exists():
            continue

        for server_dir in engine_dir.iterdir():
            if not server_dir.is_dir():
                continue
            server_name = server_dir.name

            for file_path in server_dir.iterdir():
                if file_path.is_file():
                    # Check extension
                    if file_path.name.endswith((".backup", ".ttl.gz", ".gz", ".sql")):
                        try:
                            stat = file_path.stat()
                            mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
                            parsed = parse_backup_file(file_path)
                            db_name = parsed.db_name if parsed else file_path.name.split("_")[0]
                            rel = f"{engine_type}/{server_name}/{file_path.name}"

                            files_list.append(
                                BackupFileItem(
                                    file_name=file_path.name,
                                    relative_path=rel,
                                    server_type=engine_type,
                                    server_name=server_name,
                                    database_name=db_name,
                                    size_bytes=stat.st_size,
                                    size_formatted=format_bytes(stat.st_size),
                                    modified_at=mtime,
                                    gfs_tier=None
                                )
                            )
                        except Exception:
                            continue

    # Sort newest first
    files_list.sort(key=lambda x: x.modified_at, reverse=True)
    return files_list


@router.get("/download/{file_path:path}")
async def download_backup_file(
    file_path: str,
    current_user: User = Depends(get_current_user)
):
    """Stream and download an existing backup file."""
    target_file = sanitize_relative_path(file_path)
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fichier de sauvegarde introuvable")

    return FileResponse(
        path=str(target_file),
        filename=target_file.name,
        media_type="application/octet-stream"
    )


@router.delete("/{file_path:path}")
async def delete_backup_file(
    file_path: str,
    current_user: User = Depends(get_current_user)
):
    """Physically delete a backup file from storage."""
    target_file = sanitize_relative_path(file_path)
    if not target_file.exists() or not target_file.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fichier de sauvegarde introuvable")

    try:
        target_file.unlink()
        return {"message": f"Fichier '{target_file.name}' supprimé avec succès"}
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la suppression: {exc}"
        )


@router.post("/instant", response_model=BackupLogOut)
async def trigger_instant_backup(
    payload: InstantBackupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Trigger an on-demand immediate backup for a specific database without scheduling."""
    server = await db.get(Server, payload.server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serveur introuvable")

    # Temporary ephemeral or mock Job object
    temp_job = Job(
        id=0,
        name=f"Sauvegarde Manuelle - {payload.database_name}",
        server_id=server.id,
        database_name=payload.database_name,
        cron_expression="manual",
        is_active=True,
        retention_daily=7,
        retention_weekly=4,
        retention_monthly=12
    )

    now = datetime.now(timezone.utc)
    log_entry = BackupLog(
        job_id=None,
        job_name=temp_job.name,
        server_name=server.name,
        server_type=server.server_type,
        database_name=payload.database_name,
        status="running",
        started_at=now,
        gfs_tier="manual"
    )
    db.add(log_entry)
    await db.commit()
    await db.refresh(log_entry)

    backup_root = settings.effective_backup_path
    success, file_path, file_size, duration, err_msg = await run_backup_for_job(
        server=server,
        job=temp_job,
        backup_root=backup_root
    )

    log_entry.finished_at = datetime.now(timezone.utc)
    log_entry.duration_seconds = duration

    if success:
        log_entry.status = "success"
        log_entry.file_path = str(file_path)
        log_entry.file_size_bytes = file_size
        log_entry.error_message = None
    else:
        log_entry.status = "failed"
        log_entry.error_message = err_msg

    await db.commit()
    await db.refresh(log_entry)

    return BackupLogOut.model_validate(log_entry)
