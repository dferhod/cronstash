from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import NotificationConfig, User
from app.schemas.schemas import (
    NotificationConfigOut,
    NotificationConfigUpdate,
    TestNotificationResult
)
from app.api.deps import get_current_user
from app.services.notifications import test_smtp_configuration, test_discord_configuration

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationConfigOut)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve SMTP and Discord notification settings."""
    stmt = select(NotificationConfig).limit(1)
    res = await db.execute(stmt)
    cfg = res.scalar_one_or_none()
    if not cfg:
        # Create default
        cfg = NotificationConfig()
        db.add(cfg)
        await db.commit()
        await db.refresh(cfg)
    return NotificationConfigOut.model_validate(cfg)


@router.put("", response_model=NotificationConfigOut)
async def update_notification_settings(
    payload: NotificationConfigUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update notification settings."""
    stmt = select(NotificationConfig).limit(1)
    res = await db.execute(stmt)
    cfg = res.scalar_one_or_none()
    if not cfg:
        cfg = NotificationConfig()
        db.add(cfg)

    cfg.smtp_enabled = payload.smtp_enabled
    cfg.smtp_host = payload.smtp_host
    cfg.smtp_port = payload.smtp_port
    cfg.smtp_username = payload.smtp_username
    if payload.smtp_password != "":
        cfg.smtp_password = payload.smtp_password
    cfg.smtp_use_tls = payload.smtp_use_tls
    cfg.smtp_from = payload.smtp_from
    cfg.smtp_to = payload.smtp_to

    cfg.discord_enabled = payload.discord_enabled
    cfg.discord_webhook_url = payload.discord_webhook_url

    cfg.notify_on_success = payload.notify_on_success
    cfg.notify_on_failure = payload.notify_on_failure

    await db.commit()
    await db.refresh(cfg)
    return NotificationConfigOut.model_validate(cfg)


@router.post("/test-smtp", response_model=TestNotificationResult)
async def trigger_test_smtp(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send an immediate test email using current or saved SMTP settings."""
    stmt = select(NotificationConfig).limit(1)
    res = await db.execute(stmt)
    cfg = res.scalar_one_or_none()
    if not cfg or not cfg.smtp_host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Le serveur SMTP n'est pas encore configuré."
        )

    success, msg = await test_smtp_configuration(cfg)
    return TestNotificationResult(success=success, message=msg)


@router.post("/test-discord", response_model=TestNotificationResult)
async def trigger_test_discord(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Send a formatted test embed to configured Discord Webhook."""
    stmt = select(NotificationConfig).limit(1)
    res = await db.execute(stmt)
    cfg = res.scalar_one_or_none()
    if not cfg or not cfg.discord_webhook_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="L'URL du Webhook Discord n'est pas renseignée."
        )

    success, msg = await test_discord_configuration(cfg.discord_webhook_url)
    return TestNotificationResult(success=success, message=msg)
