import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Cronstash"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Paths (Debian 13 production target with automatic local development fallbacks)
    DB_PATH: str = os.getenv("CRONSTASH_DB_PATH", "/var/lib/cronstash/cronstash.db")
    BACKUP_PATH: str = os.getenv("CRONSTASH_BACKUP_PATH", "/backup/cronstash")
    CRON_FILE_PATH: str = os.getenv("CRONSTASH_CRON_FILE", "/etc/cron.d/cronstash")
    CRON_LOG_PATH: str = os.getenv("CRONSTASH_CRON_LOG", "/var/log/cronstash/cron.log")
    APP_ROOT: str = os.getenv("CRONSTASH_APP_ROOT", "/opt/cronstash")
    PYTHON_VENV_PATH: str = os.getenv("CRONSTASH_PYTHON", "/opt/cronstash/venv/bin/python")

    # Security & JWT
    SECRET_KEY: str = os.getenv(
        "CRONSTASH_SECRET_KEY",
        "cronstash-super-secret-production-key-change-me-in-prod-argon2id-jwt-2026"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    COOKIE_NAME: str = "cronstash_token"
    COOKIE_SECURE: bool = os.getenv("CRONSTASH_COOKIE_SECURE", "false").lower() in ("true", "1")
    COOKIE_SAMESITE: str = "strict"

    # Default Admin initialization
    DEFAULT_ADMIN_USER: str = os.getenv("CRONSTASH_DEFAULT_ADMIN", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("CRONSTASH_DEFAULT_PASSWORD", "Cronstash2026!Secure")

    # Command binaries
    PG_DUMP_BIN: str = os.getenv("PG_DUMP_BIN", "pg_dump")
    CURL_BIN: str = os.getenv("CURL_BIN", "curl")
    GZIP_BIN: str = os.getenv("GZIP_BIN", "gzip")

    # Dynamic path resolution to ensure directories exist and avoid permission crashes in dev
    @property
    def effective_db_path(self) -> Path:
        target = Path(self.DB_PATH)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Test write access to directory
            test_file = target.parent / ".perm_check"
            test_file.touch(exist_ok=True)
            test_file.unlink(missing_ok=True)
            return target
        except (PermissionError, OSError):
            fallback_dir = Path("./data").resolve()
            fallback_dir.mkdir(parents=True, exist_ok=True)
            return fallback_dir / "cronstash.db"

    @property
    def effective_backup_path(self) -> Path:
        target = Path(self.BACKUP_PATH)
        try:
            target.mkdir(parents=True, exist_ok=True)
            (target / "pgsql").mkdir(parents=True, exist_ok=True)
            (target / "rdf4j").mkdir(parents=True, exist_ok=True)
            return target
        except (PermissionError, OSError):
            fallback_dir = Path("./backups").resolve()
            fallback_dir.mkdir(parents=True, exist_ok=True)
            (fallback_dir / "pgsql").mkdir(parents=True, exist_ok=True)
            (fallback_dir / "rdf4j").mkdir(parents=True, exist_ok=True)
            return fallback_dir

    @property
    def effective_cron_file(self) -> Path:
        target = Path(self.CRON_FILE_PATH)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            test_file = target.parent / ".perm_check_cron"
            test_file.touch(exist_ok=True)
            test_file.unlink(missing_ok=True)
            return target
        except (PermissionError, OSError):
            fallback_file = Path("./data/cron.d_cronstash").resolve()
            fallback_file.parent.mkdir(parents=True, exist_ok=True)
            return fallback_file

    @property
    def sqlite_async_url(self) -> str:
        # Convert path to sqlite+aiosqlite URI
        p = str(self.effective_db_path).replace("\\", "/")
        return f"sqlite+aiosqlite:///{p}"

    class Config:
        case_sensitive = True


settings = Settings()
