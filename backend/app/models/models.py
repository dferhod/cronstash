from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Float,
    Text,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    server_type = Column(String(20), nullable=False)  # "postgresql" or "rdf4j"
    host = Column(String(255), nullable=False)
    port = Column(Integer, nullable=False, default=5432)
    username = Column(String(100), nullable=True)
    password = Column(String(255), nullable=True)
    extra_params = Column(Text, nullable=True)  # JSON or extra config options
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    jobs = relationship("Job", back_populates="server", cascade="all, delete-orphan", lazy="selectin")


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    database_name = Column(String(150), nullable=False)  # PG db or RDF4J repository ID
    cron_expression = Column(String(100), nullable=False, default="0 2 * * *")
    is_active = Column(Boolean, default=True, nullable=False)
    
    # GFS retention parameters (N1, N2, N3)
    retention_daily = Column(Integer, default=7, nullable=False)    # N1: Son
    retention_weekly = Column(Integer, default=4, nullable=False)   # N2: Father
    retention_monthly = Column(Integer, default=12, nullable=False) # N3: Grandfather

    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    # Relationships
    server = relationship("Server", back_populates="jobs", lazy="selectin")
    logs = relationship("BackupLog", back_populates="job", cascade="all, delete-orphan", lazy="selectin")


class BackupLog(Base):
    __tablename__ = "backup_logs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True)
    job_name = Column(String(150), nullable=False)
    server_name = Column(String(100), nullable=False)
    server_type = Column(String(20), nullable=False)
    database_name = Column(String(150), nullable=False)
    status = Column(String(20), nullable=False)  # "success", "failed", "running"
    
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    file_path = Column(String(500), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    gfs_tier = Column(String(50), nullable=True)  # "daily", "weekly", "monthly", "manual"
    error_message = Column(Text, nullable=True)
    purged_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    # Relationships
    job = relationship("Job", back_populates="logs", lazy="selectin")


class NotificationConfig(Base):
    __tablename__ = "notification_config"

    id = Column(Integer, primary_key=True)
    smtp_enabled = Column(Boolean, default=False, nullable=False)
    smtp_host = Column(String(255), default="", nullable=False)
    smtp_port = Column(Integer, default=587, nullable=False)
    smtp_username = Column(String(150), default="", nullable=False)
    smtp_password = Column(String(255), default="", nullable=False)
    smtp_use_tls = Column(Boolean, default=True, nullable=False)
    smtp_from = Column(String(255), default="", nullable=False)
    smtp_to = Column(String(255), default="", nullable=False)

    discord_enabled = Column(Boolean, default=False, nullable=False)
    discord_webhook_url = Column(String(500), default="", nullable=False)

    notify_on_success = Column(Boolean, default=False, nullable=False)
    notify_on_failure = Column(Boolean, default=True, nullable=False)

    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)
