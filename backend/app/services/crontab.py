import os
import sys
import logging
from pathlib import Path
from typing import List, Tuple
from app.core.config import settings
from app.models.models import Job

logger = logging.getLogger("cronstash.crontab")


def generate_cron_content(jobs: List[Job]) -> str:
    """
    Generates crontab file content adhering to Debian /etc/cron.d/ standards:
    
    SHELL=/bin/bash
    PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

    # Job ID <id>
    <cron_expression> root /opt/cronstash/venv/bin/python /opt/cronstash/cli.py run-job --id <id> >> /var/log/cronstash/cron.log 2>&1
    """
    lines = [
        "SHELL=/bin/bash",
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "# Generated automatically by Cronstash - Do not edit manually",
        ""
    ]

    active_jobs = [j for j in jobs if j.is_active]

    if not active_jobs:
        lines.append("# No active backup jobs configured.")
        lines.append("")
        return "\n".join(lines)

    for job in active_jobs:
        clean_expr = job.cron_expression.strip()
        lines.append(f"# Job ID {job.id} : {job.name} ({job.database_name})")
        # Target path: python /opt/cronstash/cli.py run-job --id <id>
        cli_path = "/opt/cronstash/cli.py"
        python_bin = settings.PYTHON_VENV_PATH
        log_file = settings.CRON_LOG_PATH
        
        cron_line = f"{clean_expr} root {python_bin} {cli_path} run-job --id {job.id} >> {log_file} 2>&1"
        lines.append(cron_line)
        lines.append("")

    return "\n".join(lines)


def sync_system_crontab(jobs: List[Job]) -> Tuple[bool, str]:
    """
    Writes the crontab file to /etc/cron.d/cronstash (or fallback path).
    Ensures correct permissions (0644) required by cron on Debian.
    """
    from typing import Tuple
    content = generate_cron_content(jobs)
    target_file = settings.effective_cron_file

    try:
        # Atomic write via temp file in same directory
        temp_file = target_file.parent / f".{target_file.name}.tmp"
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(content)

        # Set permissions to 0644 (Debian requirement: non-executable, readable by owner and world)
        if sys.platform != "win32":
            try:
                os.chmod(temp_file, 0o644)
            except Exception as e:
                logger.warning(f"Could not chmod crontab file: {e}")

        # Replace target
        temp_file.replace(target_file)
        logger.info(f"Synchronized crontab successfully at {target_file}")
        return True, f"Crontab synchronisé avec succès ({target_file})"
    except (PermissionError, OSError) as exc:
        logger.error(f"Failed to write system crontab at {target_file}: {exc}")
        # Try fallback to local dev path
        fallback = Path("./data/cron.d_cronstash").resolve()
        fallback.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(fallback, "w", encoding="utf-8") as f:
                f.write(content)
            return True, f"Crontab écrit dans le fichier local de secours: {fallback}"
        except Exception as fb_exc:
            return False, f"Erreur critique d'écriture crontab: {exc} | {fb_exc}"
