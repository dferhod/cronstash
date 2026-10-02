import os
import sys
import time
import shutil
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple
import httpx
from app.core.config import settings
from app.models.models import Server, Job

logger = logging.getLogger("cronstash.executor")


def get_timestamp_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def sanitize_filename(name: str) -> str:
    """Ensure filenames contain only safe characters."""
    return "".join(c if c.isalnum() or c in ("-", "_", ".") else "_" for c in name)


async def execute_postgresql_backup(
    server: Server,
    job: Job,
    backup_root: Path
) -> Tuple[bool, Path, int, float, str]:
    """
    Executes pg_dump for PostgreSQL 18:
    pg_dump -h <host> -p <port> -U <user> -F c -b -v -f /backup/cronstash/pgsql/<server_name>/<db>_<timestamp>.backup <db>
    """
    start_time = time.monotonic()
    safe_server_name = sanitize_filename(server.name)
    safe_db_name = sanitize_filename(job.database_name)
    target_dir = backup_root / "pgsql" / safe_server_name
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = get_timestamp_str()
    output_file = target_dir / f"{safe_db_name}_{timestamp}.backup"

    env = os.environ.copy()
    if server.password:
        env["PGPASSWORD"] = server.password

    cmd = [
        settings.PG_DUMP_BIN,
        "-h", str(server.host),
        "-p", str(server.port),
        "-U", str(server.username or "postgres"),
        "-F", "c",
        "-b",
        "-v",
        "-f", str(output_file),
        job.database_name
    ]

    logger.info(f"Starting PostgreSQL backup for job '{job.name}' (DB: {job.database_name}) to {output_file}")

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        stdout, stderr = await process.communicate()
        duration = round(time.monotonic() - start_time, 2)

        if process.returncode != 0:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            logger.error(f"pg_dump failed with returncode {process.returncode}: {error_msg}")
            # Clean up empty/corrupted backup file if it exists
            if output_file.exists() and output_file.stat().st_size == 0:
                output_file.unlink(missing_ok=True)
            return False, output_file, 0, duration, f"pg_dump code {process.returncode}: {error_msg}"

        file_size = output_file.stat().st_size if output_file.exists() else 0
        logger.info(f"PostgreSQL backup completed: {output_file} ({file_size} bytes in {duration}s)")
        return True, output_file, file_size, duration, ""

    except FileNotFoundError:
        duration = round(time.monotonic() - start_time, 2)
        err = f"Binaire '{settings.PG_DUMP_BIN}' introuvable. Veuillez vérifier l'installation de postgresql-client."
        logger.error(err)
        return False, output_file, 0, duration, err
    except Exception as exc:
        duration = round(time.monotonic() - start_time, 2)
        logger.exception(f"Unexpected exception during PostgreSQL backup: {exc}")
        return False, output_file, 0, duration, str(exc)


async def execute_rdf4j_backup(
    server: Server,
    job: Job,
    backup_root: Path
) -> Tuple[bool, Path, int, float, str]:
    """
    Executes RDF4J backup via subprocess streaming or python streaming into gzip:
    curl -s -S -H "Accept: application/x-turtle" "<rdf4j_url>/repositories/<repo_id>/statements" | gzip > /backup/cronstash/rdf4j/<server_name>/<repo>_<timestamp>.ttl.gz
    """
    start_time = time.monotonic()
    safe_server_name = sanitize_filename(server.name)
    safe_repo_name = sanitize_filename(job.database_name)
    target_dir = backup_root / "rdf4j" / safe_server_name
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = get_timestamp_str()
    output_file = target_dir / f"{safe_repo_name}_{timestamp}.ttl.gz"

    # Construct source URL
    if server.host.startswith("http://") or server.host.startswith("https://"):
        base_url = server.host
    else:
        scheme = "https" if server.port == 443 else "http"
        base_url = f"{scheme}://{server.host}:{server.port}"

    endpoint = f"{base_url.rstrip('/')}/repositories/{job.database_name}/statements"

    logger.info(f"Starting RDF4J backup for job '{job.name}' (Repo: {job.database_name}) from {endpoint}")

    # Primary method: subprocess pipeline if bash/sh is available (Linux Debian 13 target)
    is_unix = sys.platform != "win32"
    if is_unix and shutil.which("curl") and shutil.which("gzip"):
        # Format curl with auth if present
        auth_opt = f"-u '{server.username}:{server.password}' " if (server.username and server.password) else ""
        shell_cmd = (
            f"set -o pipefail; "
            f"curl -fsSL {auth_opt}-H 'Accept: text/turtle, application/x-turtle' '{endpoint}' "
            f"| gzip > '{output_file}'"
        )
        try:
            proc = await asyncio.create_subprocess_shell(
                shell_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                executable="/bin/bash" if Path("/bin/bash").exists() else "/bin/sh"
            )
            stdout, stderr = await proc.communicate()
            duration = round(time.monotonic() - start_time, 2)

            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                if output_file.exists():
                    output_file.unlink(missing_ok=True)
                return False, output_file, 0, duration, f"Subprocess error ({proc.returncode}): {err_msg}"

            file_size = output_file.stat().st_size if output_file.exists() else 0
            # Check if gzip produced at least header size (>20 bytes)
            if file_size < 30:
                # May be empty or error response
                pass

            return True, output_file, file_size, duration, ""
        except Exception as exc:
            logger.warning(f"Subprocess curl|gzip failed: {exc}. Falling back to Python streaming gzip...")

    # Robust streaming HTTP client fallback (works universally on all platforms and tests HTTP status cleanly)
    import gzip
    auth = (server.username, server.password) if (server.username and server.password) else None
    headers = {"Accept": "application/x-turtle"}

    try:
        async with httpx.AsyncClient(timeout=300.0, verify=False) as client:
            async with client.stream("GET", endpoint, headers=headers, auth=auth) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    duration = round(time.monotonic() - start_time, 2)
                    err = f"Erreur HTTP RDF4J {response.status_code}: {body.decode('utf-8', errors='replace')[:300]}"
                    return False, output_file, 0, duration, err

                def _write_gzip():
                    with open(output_file, "wb") as f_out:
                        with gzip.GzipFile(fileobj=f_out, mode="wb", mtime=0) as gz_out:
                            for chunk in response.iter_bytes(chunk_size=65536):
                                gz_out.write(chunk)

                await asyncio.to_thread(_write_gzip)

        duration = round(time.monotonic() - start_time, 2)
        file_size = output_file.stat().st_size if output_file.exists() else 0
        return True, output_file, file_size, duration, ""

    except Exception as exc:
        duration = round(time.monotonic() - start_time, 2)
        if output_file.exists():
            output_file.unlink(missing_ok=True)
        logger.exception(f"RDF4J streaming backup error: {exc}")
        return False, output_file, 0, duration, str(exc)


async def run_backup_for_job(
    server: Server,
    job: Job,
    backup_root: Path
) -> Tuple[bool, Path, int, float, str]:
    """Dispatch backup execution according to server type."""
    if server.server_type == "postgresql":
        return await execute_postgresql_backup(server, job, backup_root)
    elif server.server_type == "rdf4j":
        return await execute_rdf4j_backup(server, job, backup_root)
    else:
        raise ValueError(f"Type de serveur de sauvegarde non pris en charge: {server.server_type}")
