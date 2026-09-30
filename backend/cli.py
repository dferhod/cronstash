#!/usr/bin/env python3
import sys
import os
import argparse
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

# Add backend directory to sys.path so app modules can be imported
sys_path_root = Path(__file__).resolve().parent
if str(sys_path_root) not in sys.path:
    sys.path.insert(0, str(sys_path_root))

from app.core.config import settings
from app.core.database import AsyncSessionLocal, init_db
from app.core.security import hash_password
from app.models.models import Job, Server, BackupLog, NotificationConfig, User
from app.services.executor import run_backup_for_job
from app.services.gfs import apply_gfs_purge
from app.services.notifications import dispatch_notifications_for_log
from app.services.crontab import sync_system_crontab
from sqlalchemy import select

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [Cronstash-CLI] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("cronstash.cli")


async def run_job_by_id(job_id: int, force: bool = False) -> int:
    """Execute a single backup job by its ID, run GFS retention, and dispatch notifications."""
    await init_db()

    async with AsyncSessionLocal() as session:
        # Load Job with Server
        stmt = select(Job).where(Job.id == job_id)
        res = await session.execute(stmt)
        job = res.scalar_one_or_none()

        if not job:
            logger.error(f"Job ID {job_id} introuvable dans la base de données.")
            return 1

        if not job.is_active and not force:
            logger.warning(f"Le Job '{job.name}' (ID: {job_id}) est désactivé. Utilisez --force pour l'exécuter.")
            return 0

        server = job.server
        if not server:
            logger.error(f"Serveur associé au job ID {job_id} introuvable.")
            return 1

        logger.info(f"=== Lancement du Job: '{job.name}' (Serveur: {server.name} [{server.server_type}], Base: {job.database_name}) ===")

        # Create running log entry
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
        session.add(log_entry)
        await session.commit()
        await session.refresh(log_entry)

        # Run backup
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

            # Compute next run time if croniter is present
            try:
                from croniter import croniter
                iter_cron = croniter(job.cron_expression, job.last_run_at)
                job.next_run_at = iter_cron.get_next(datetime)
            except Exception as e:
                logger.debug(f"Impossible de calculer la prochaine exécution: {e}")

            # Apply GFS Retention Purge
            parent_dir = file_path.parent
            logger.info(f"Exécution de la politique de rétention GFS dans {parent_dir} (N1={job.retention_daily}, N2={job.retention_weekly}, N3={job.retention_monthly})")
            gfs_result = apply_gfs_purge(
                target_dir=parent_dir,
                database_name=job.database_name,
                n1_daily=job.retention_daily,
                n2_weekly=job.retention_weekly,
                n3_monthly=job.retention_monthly
            )

            purged_count = gfs_result.get("purged_count", 0)
            freed_bytes = gfs_result.get("bytes_freed", 0)
            tiers_map = gfs_result.get("tiers_map", {})
            current_tiers = tiers_map.get(file_path.name, ["daily"])
            log_entry.gfs_tier = ", ".join(current_tiers) if current_tiers else "daily"

            logger.info(f"Purge GFS terminée: {purged_count} archive(s) supprimée(s), {freed_bytes / (1024*1024):.2f} Mo libérés.")
            logger.info(f"Sauvegarde RÉUSSIE : {file_path.name} ({file_size} octets en {duration}s)")
        else:
            log_entry.status = "failed"
            log_entry.error_message = err_msg
            logger.error(f"Sauvegarde ÉCHOUÉE pour le job '{job.name}': {err_msg}")

        # Dispatch notifications
        notif_stmt = select(NotificationConfig).limit(1)
        notif_res = await session.execute(notif_stmt)
        notif_config = notif_res.scalar_one_or_none()

        if notif_config:
            try:
                await dispatch_notifications_for_log(notif_config, log_entry)
            except Exception as e:
                logger.error(f"Erreur lors de l'envoi des notifications: {e}")

        await session.commit()
        return 0 if success else 1


async def init_admin_cmd(username: str, password: str) -> int:
    """Initialize or update administrator credentials."""
    await init_db()
    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.username == username)
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        if user:
            user.password_hash = hash_password(password)
            logger.info(f"Mot de passe administrateur pour '{username}' mis à jour avec succès.")
        else:
            user = User(
                username=username,
                password_hash=hash_password(password)
            )
            session.add(user)
            logger.info(f"Compte administrateur '{username}' créé avec succès.")

        await session.commit()
        return 0


async def sync_cron_cmd() -> int:
    """Regenerate crontab file from active database jobs."""
    await init_db()
    async with AsyncSessionLocal() as session:
        stmt = select(Job)
        res = await session.execute(stmt)
        jobs = res.scalars().all()

        ok, msg = sync_system_crontab(list(jobs))
        if ok:
            logger.info(msg)
            return 0
        else:
            logger.error(msg)
            return 1


async def list_jobs_cmd() -> int:
    """List configured jobs."""
    await init_db()
    async with AsyncSessionLocal() as session:
        stmt = select(Job)
        res = await session.execute(stmt)
        jobs = res.scalars().all()

        print(f"\n{'ID':<5} {'NOM':<25} {'SERVEUR':<15} {'BASE':<20} {'CRON':<15} {'ACTIF':<6} {'N1/N2/N3'}")
        print("-" * 95)
        for j in jobs:
            s_name = j.server.name if j.server else "N/A"
            status = "Oui" if j.is_active else "Non"
            gfs = f"{j.retention_daily}/{j.retention_weekly}/{j.retention_monthly}"
            print(f"{j.id:<5} {j.name:<25} {s_name:<15} {j.database_name:<20} {j.cron_expression:<15} {status:<6} {gfs}")
        print("")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Cronstash CLI - Backup Engine & Scheduler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run-job command: python /opt/cronstash/cli.py run-job --id <id>
    run_parser = subparsers.add_parser("run-job", help="Exécuter une tâche de sauvegarde spécifique")
    run_parser.add_argument("--id", type=int, required=True, help="Identifiant du job à exécuter")
    run_parser.add_argument("--force", action="store_true", help="Forcer l'exécution même si le job est inactif")

    # init-admin command
    admin_parser = subparsers.add_parser("init-admin", help="Créer ou mettre à jour le compte administrateur")
    admin_parser.add_argument("--username", type=str, default="admin", help="Nom d'utilisateur")
    admin_parser.add_argument("--password", type=str, required=True, help="Mot de passe")

    # sync-cron command
    subparsers.add_parser("sync-cron", help="Régénérer le fichier de crontab système /etc/cron.d/cronstash")

    # list-jobs command
    subparsers.add_parser("list-jobs", help="Lister toutes les tâches de sauvegarde")

    args = parser.parse_args()

    if args.command == "run-job":
        code = asyncio.run(run_job_by_id(args.id, force=args.force))
        sys.exit(code)
    elif args.command == "init-admin":
        code = asyncio.run(init_admin_cmd(args.username, args.password))
        sys.exit(code)
    elif args.command == "sync-cron":
        code = asyncio.run(sync_cron_cmd())
        sys.exit(code)
    elif args.command == "list-jobs":
        code = asyncio.run(list_jobs_cmd())
        sys.exit(code)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
