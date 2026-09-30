import os
import re
import logging
from datetime import datetime, date, timezone
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any

logger = logging.getLogger("cronstash.gfs")

FILENAME_REGEX = re.compile(r"^(?P<dbname>.+)_(?P<dt>\d{8}_\d{6})\.(?P<ext>backup|ttl\.gz|gz|sql)$")


class BackupFileInfo:
    def __init__(self, path: Path, file_date: datetime, db_name: str):
        self.path = path
        self.dt = file_date
        self.date_only = file_date.date()
        self.db_name = db_name
        self.size = path.stat().st_size if path.exists() else 0
        self.assigned_tiers: Set[str] = set()

    def __repr__(self) -> str:
        return f"<BackupFile {self.path.name} {self.dt.isoformat()}>"


def parse_backup_file(path: Path) -> Optional[BackupFileInfo]:
    """Parse backup file name and extract database name and date/time."""
    match = FILENAME_REGEX.match(path.name)
    if match:
        dbname = match.group("dbname")
        dt_str = match.group("dt")
        try:
            dt = datetime.strptime(dt_str, "%Y%m%d_%H%M%S").replace(tzinfo=timezone.utc)
            return BackupFileInfo(path, dt, dbname)
        except ValueError:
            pass

    # Fallback using mtime if naming convention differs slightly
    try:
        mtime = path.stat().st_mtime
        dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
        prefix = path.name.split("_")[0] if "_" in path.name else path.stem
        return BackupFileInfo(path, dt, prefix)
    except Exception:
        return None


def calculate_gfs_retention(
    files: List[BackupFileInfo],
    n1_daily: int = 7,
    n2_weekly: int = 4,
    n3_monthly: int = 12
) -> Tuple[Set[Path], Set[Path], Dict[str, Set[str]]]:
    """
    Applies the GFS (Grandfather-Father-Son) retention policy:
    - Son (Daily): retain N1 most recent days (1 backup per day).
    - Father (Weekly): retain N2 weekly backups (preferably taken on Sunday).
    - Grandfather (Monthly): retain N3 monthly backups (preferably taken on the 1st of the month).

    Returns:
    - retained_paths: set of Path objects to keep
    - purged_paths: set of Path objects to delete
    - tiers_map: filename -> set of assigned tiers {"daily", "weekly", "monthly"}
    """
    if not files:
        return set(), set(), {}

    # Sort files from newest to oldest
    files_sorted = sorted(files, key=lambda f: f.dt, reverse=True)

    retained_files: Set[BackupFileInfo] = set()

    # 1. SON (Daily retention: N1 most recent days)
    # Group by day, keeping the newest file of each day
    daily_groups: Dict[date, BackupFileInfo] = {}
    for f in files_sorted:
        d = f.date_only
        if d not in daily_groups:
            daily_groups[d] = f

    sorted_days = sorted(daily_groups.keys(), reverse=True)
    for day in sorted_days[:n1_daily]:
        chosen = daily_groups[day]
        chosen.assigned_tiers.add("daily")
        retained_files.add(chosen)

    # 2. FATHER (Weekly retention: N2 weeks)
    # Group files by ISO year and week
    week_groups: Dict[Tuple[int, int], List[BackupFileInfo]] = {}
    for f in files_sorted:
        iso_year, iso_week, _ = f.date_only.isocalendar()
        key = (iso_year, iso_week)
        week_groups.setdefault(key, []).append(f)

    # Sort weeks from newest to oldest
    sorted_weeks = sorted(week_groups.keys(), reverse=True)
    for week_key in sorted_weeks[:n2_weekly]:
        week_files = week_groups[week_key]
        # Prefer file taken on Sunday (weekday 6)
        sunday_file = next((f for f in week_files if f.date_only.weekday() == 6), None)
        chosen = sunday_file if sunday_file else week_files[0]
        chosen.assigned_tiers.add("weekly")
        retained_files.add(chosen)

    # 3. GRANDFATHER (Monthly retention: N3 months)
    # Group files by Year and Month
    month_groups: Dict[Tuple[int, int], List[BackupFileInfo]] = {}
    for f in files_sorted:
        key = (f.date_only.year, f.date_only.month)
        month_groups.setdefault(key, []).append(f)

    sorted_months = sorted(month_groups.keys(), reverse=True)
    for month_key in sorted_months[:n3_monthly]:
        m_files = month_groups[month_key]
        # Prefer file taken on 1st of month (day == 1)
        first_day_file = next((f for f in m_files if f.date_only.day == 1), None)
        chosen = first_day_file if first_day_file else m_files[-1]  # or earliest file in that month
        chosen.assigned_tiers.add("monthly")
        retained_files.add(chosen)

    retained_paths = {f.path for f in retained_files}
    all_paths = {f.path for f in files}
    purged_paths = all_paths - retained_paths

    tiers_map = {f.path.name: f.assigned_tiers for f in retained_files}

    return retained_paths, purged_paths, tiers_map


def apply_gfs_purge(
    target_dir: Path,
    database_name: str,
    n1_daily: int = 7,
    n2_weekly: int = 4,
    n3_monthly: int = 12
) -> Dict[str, Any]:
    """
    Scans the given target directory for backups of database_name,
    calculates GFS policy, removes orphaned/outdated files from disk,
    and returns a summary report.
    """
    if not target_dir.exists():
        return {
            "purged_count": 0,
            "bytes_freed": 0,
            "purged_files": [],
            "retained_count": 0
        }

    # Find all files matching database prefix
    candidate_files: List[BackupFileInfo] = []
    for item in target_dir.iterdir():
        if item.is_file():
            info = parse_backup_file(item)
            if info and info.db_name == database_name:
                candidate_files.append(info)

    retained_paths, purged_paths, tiers_map = calculate_gfs_retention(
        candidate_files,
        n1_daily=n1_daily,
        n2_weekly=n2_weekly,
        n3_monthly=n3_monthly
    )

    purged_list = []
    bytes_freed = 0

    for path_to_purge in purged_paths:
        try:
            sz = path_to_purge.stat().st_size
            path_to_purge.unlink(missing_ok=True)
            bytes_freed += sz
            purged_list.append(path_to_purge.name)
            logger.info(f"GFS purge: deleted outdated backup '{path_to_purge.name}' ({sz} bytes freed)")
        except Exception as exc:
            logger.error(f"Failed to delete backup file '{path_to_purge}': {exc}")

    return {
        "purged_count": len(purged_list),
        "bytes_freed": bytes_freed,
        "purged_files": purged_list,
        "retained_count": len(retained_paths),
        "tiers_map": {k: list(v) for k, v in tiers_map.items()}
    }
