from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


# ===================== AUTH SCHEMAS =====================

class LoginRequest(BaseModel):
    username: str = Field(..., description="Nom d'utilisateur admin")
    password: str = Field(..., description="Mot de passe")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    created_at: datetime


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, description="Au moins 8 caractères")


# ===================== SERVER SCHEMAS =====================

class ServerBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    server_type: str = Field(..., pattern="^(postgresql|rdf4j)$")
    host: str = Field(..., min_length=1)
    port: int = Field(default=5432, ge=1, le=65535)
    username: Optional[str] = None
    extra_params: Optional[str] = None


class ServerCreate(ServerBase):
    password: Optional[str] = None


class ServerUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    server_type: Optional[str] = Field(None, pattern="^(postgresql|rdf4j)$")
    host: Optional[str] = None
    port: Optional[int] = Field(None, ge=1, le=65535)
    username: Optional[str] = None
    password: Optional[str] = None
    extra_params: Optional[str] = None


class ServerOut(ServerBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    has_password: bool = False
    created_at: datetime
    updated_at: datetime


class DiscoveredDatabase(BaseModel):
    name: str
    title: Optional[str] = None
    size_formatted: Optional[str] = None
    already_monitored: bool = False


class ServerDiscoveryResponse(BaseModel):
    server_id: int
    server_name: str
    server_type: str
    databases: List[DiscoveredDatabase]


# ===================== JOB SCHEMAS =====================

class JobBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=150)
    server_id: int
    database_name: str
    cron_expression: str = Field(default="0 2 * * *")
    is_active: bool = True
    retention_daily: int = Field(default=7, ge=1, le=365)
    retention_weekly: int = Field(default=4, ge=0, le=104)
    retention_monthly: int = Field(default=12, ge=0, le=120)


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    name: Optional[str] = None
    server_id: Optional[int] = None
    database_name: Optional[str] = None
    cron_expression: Optional[str] = None
    is_active: Optional[bool] = None
    retention_daily: Optional[int] = Field(None, ge=1, le=365)
    retention_weekly: Optional[int] = Field(None, ge=0, le=104)
    retention_monthly: Optional[int] = Field(None, ge=0, le=120)


class JobOut(JobBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    server_name: Optional[str] = None
    server_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ===================== BACKUP LOG SCHEMAS =====================

class BackupLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    job_id: Optional[int] = None
    job_name: str
    server_name: str
    server_type: str
    database_name: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    gfs_tier: Optional[str] = None
    error_message: Optional[str] = None
    purged_at: Optional[datetime] = None
    created_at: datetime


# ===================== BACKUP FILE SCHEMAS =====================

class BackupFileItem(BaseModel):
    file_name: str
    relative_path: str
    server_type: str  # pgsql or rdf4j
    server_name: str
    database_name: str
    size_bytes: int
    size_formatted: str
    modified_at: datetime
    gfs_tier: Optional[str] = None


# ===================== NOTIFICATION SCHEMAS =====================

class NotificationConfigBase(BaseModel):
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from: str = ""
    smtp_to: str = ""
    discord_enabled: bool = False
    discord_webhook_url: str = ""
    notify_on_success: bool = False
    notify_on_failure: bool = True


class NotificationConfigUpdate(NotificationConfigBase):
    pass


class NotificationConfigOut(NotificationConfigBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    updated_at: datetime


class TestNotificationResult(BaseModel):
    success: bool
    message: str


# ===================== DASHBOARD SCHEMAS =====================

class DiskStats(BaseModel):
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float
    total_formatted: str
    used_formatted: str
    free_formatted: str


class Last24HoursStats(BaseModel):
    total_runs: int
    success_runs: int
    failed_runs: int
    success_rate: float


class DashboardStatsOut(BaseModel):
    disk: DiskStats
    total_servers: int
    total_jobs: int
    active_jobs: int
    stats_24h: Last24HoursStats
    recent_logs: List[BackupLogOut]
