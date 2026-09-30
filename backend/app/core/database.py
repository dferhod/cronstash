from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.core.config import settings

Base = declarative_base()

# SQLAlchemy Async Engine with SQLite foreign keys enabled
engine = create_async_engine(
    settings.sqlite_async_url,
    echo=settings.DEBUG,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency to yield an async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """Initialize database tables and create initial administrator if absent."""
    # Ensure tables exist
    async with engine.begin() as conn:
        # Enable foreign keys pragma for SQLite
        await conn.execute(
            # Pragma execution
            # sqlalchemy text
            __import__("sqlalchemy").text("PRAGMA foreign_keys = ON;")
        )
        await conn.run_sync(Base.metadata.create_all)

    # Check for admin user and default notifications
    from sqlalchemy import select
    from app.models.models import User, NotificationConfig
    from app.core.security import hash_password

    async with AsyncSessionLocal() as session:
        # Check admin
        admin_res = await session.execute(select(User).limit(1))
        existing_admin = admin_res.scalar_one_or_none()
        if not existing_admin:
            admin_user = User(
                username=settings.DEFAULT_ADMIN_USER,
                password_hash=hash_password(settings.DEFAULT_ADMIN_PASSWORD),
            )
            session.add(admin_user)

        # Check default notification config
        notif_res = await session.execute(select(NotificationConfig).limit(1))
        existing_notif = notif_res.scalar_one_or_none()
        if not existing_notif:
            default_notif = NotificationConfig(
                smtp_enabled=False,
                smtp_host="",
                smtp_port=587,
                smtp_username="",
                smtp_password="",
                smtp_use_tls=True,
                smtp_from="",
                smtp_to="",
                discord_enabled=False,
                discord_webhook_url="",
                notify_on_success=False,
                notify_on_failure=True
            )
            session.add(default_notif)

        await session.commit()
