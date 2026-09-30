import smtplib
import ssl
import logging
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timezone
from typing import Tuple, Optional
import httpx
from app.models.models import NotificationConfig, BackupLog

logger = logging.getLogger("cronstash.notifications")


def format_bytes(bytes_count: Optional[int]) -> str:
    """Format bytes count into human readable format."""
    if bytes_count is None:
        return "N/A"
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.2f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.2f} MB"
    else:
        return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"


def generate_email_html(log: BackupLog) -> str:
    """Builds a polished, responsive HTML email for backup status."""
    is_success = log.status == "success"
    status_color = "#10b981" if is_success else "#ef4444"
    status_badge = "SUCCÈS" if is_success else "ÉCHEC"
    error_block = ""

    if log.error_message:
        error_block = f"""
        <div style="margin-top: 20px; padding: 16px; background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px;">
            <p style="margin: 0 0 8px 0; font-weight: bold; color: #991b1b;">Détails de l'erreur :</p>
            <pre style="margin: 0; white-space: pre-wrap; font-family: monospace; font-size: 13px; color: #b91c1c;">{log.error_message}</pre>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Rapport de sauvegarde Cronstash</title>
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 24px; color: #1e293b;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); border: 1px solid #e2e8f0; overflow: hidden;">
            <div style="background-color: #0f172a; padding: 24px; text-align: center;">
                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700; letter-spacing: -0.5px;">Cronstash</h1>
                <p style="margin: 4px 0 0 0; color: #94a3b8; font-size: 14px;">Gestionnaire de Sauvegardes Automatiques</p>
            </div>
            
            <div style="padding: 28px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; border-bottom: 1px solid #f1f5f9; padding-bottom: 16px;">
                    <div>
                        <h2 style="margin: 0; font-size: 18px; color: #0f172a;">Rapport : {log.job_name}</h2>
                        <p style="margin: 4px 0 0 0; font-size: 13px; color: #64748b;">Exécuté le {log.started_at.strftime('%d/%m/%Y à %H:%M:%S UTC')}</p>
                    </div>
                    <span style="display: inline-block; padding: 6px 14px; border-radius: 9999px; font-size: 13px; font-weight: 700; color: #ffffff; background-color: {status_color};">
                        {status_badge}
                    </span>
                </div>

                <table style="width: 100%; border-collapse: collapse; margin-bottom: 16px;">
                    <tbody>
                        <tr style="border-bottom: 1px solid #f8fafc;">
                            <td style="padding: 10px 0; color: #64748b; font-size: 14px; width: 40%;">Serveur</td>
                            <td style="padding: 10px 0; color: #0f172a; font-size: 14px; font-weight: 600;">{log.server_name} ({log.server_type.upper()})</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #f8fafc;">
                            <td style="padding: 10px 0; color: #64748b; font-size: 14px;">Base de données / Dépôt</td>
                            <td style="padding: 10px 0; color: #0f172a; font-size: 14px; font-weight: 600;">{log.database_name}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #f8fafc;">
                            <td style="padding: 10px 0; color: #64748b; font-size: 14px;">Taille de l'archive</td>
                            <td style="padding: 10px 0; color: #0f172a; font-size: 14px; font-weight: 600;">{format_bytes(log.file_size_bytes)}</td>
                        </tr>
                        <tr style="border-bottom: 1px solid #f8fafc;">
                            <td style="padding: 10px 0; color: #64748b; font-size: 14px;">Durée d'exécution</td>
                            <td style="padding: 10px 0; color: #0f172a; font-size: 14px; font-weight: 600;">{log.duration_seconds or 0:.2f} s</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px 0; color: #64748b; font-size: 14px;">Fichier généré</td>
                            <td style="padding: 10px 0; color: #0f172a; font-size: 13px; font-family: monospace; word-break: break-all;">{log.file_path or 'Aucun'}</td>
                        </tr>
                    </tbody>
                </table>

                {error_block}
            </div>

            <div style="background-color: #f8fafc; padding: 16px 24px; text-align: center; border-top: 1px solid #e2e8f0;">
                <p style="margin: 0; font-size: 12px; color: #94a3b8;">
                    Généré automatiquement par Cronstash • Serveur Debian 13 (Trixie)
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return html


async def send_smtp_notification(config: NotificationConfig, log: BackupLog) -> Tuple[bool, str]:
    """Sends backup status email via SMTP."""
    if not config.smtp_enabled or not config.smtp_host or not config.smtp_to:
        return False, "SMTP non configuré ou désactivé"

    def _sync_send() -> Tuple[bool, str]:
        try:
            msg = MIMEMultipart("alternative")
            status_text = "Succès" if log.status == "success" else "ÉCHEC"
            msg["Subject"] = f"[{status_text}] Sauvegarde Cronstash : {log.job_name} ({log.database_name})"
            msg["From"] = config.smtp_from or config.smtp_username or "cronstash@localhost"
            msg["To"] = config.smtp_to

            # Plain text fallback
            plain_text = (
                f"Rapport Cronstash : {log.job_name}\n"
                f"Statut : {log.status}\n"
                f"Serveur : {log.server_name} ({log.server_type})\n"
                f"Base : {log.database_name}\n"
                f"Taille : {format_bytes(log.file_size_bytes)}\n"
                f"Durée : {log.duration_seconds}s\n"
                f"Erreur : {log.error_message or 'Aucune'}\n"
            )
            msg.attach(MIMEText(plain_text, "plain", "utf-8"))

            # HTML content
            html_content = generate_email_html(log)
            msg.attach(MIMEText(html_content, "html", "utf-8"))

            if config.smtp_port == 465:
                # SSL directly
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, context=context, timeout=15) as server:
                    if config.smtp_username and config.smtp_password:
                        server.login(config.smtp_username, config.smtp_password)
                    server.send_message(msg)
            else:
                # Standard SMTP + STARTTLS
                with smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15) as server:
                    server.ehlo()
                    if config.smtp_use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                        server.ehlo()
                    if config.smtp_username and config.smtp_password:
                        server.login(config.smtp_username, config.smtp_password)
                    server.send_message(msg)

            return True, "E-mail SMTP envoyé avec succès"
        except Exception as exc:
            logger.error(f"Failed to send SMTP email: {exc}")
            return False, f"Erreur SMTP: {exc}"

    return await asyncio.to_thread(_sync_send)


async def send_discord_notification(config: NotificationConfig, log: BackupLog) -> Tuple[bool, str]:
    """Sends rich Embed notification to Discord Webhook."""
    if not config.discord_enabled or not config.discord_webhook_url:
        return False, "Discord non configuré ou désactivé"

    is_success = log.status == "success"
    embed_color = 0x10B981 if is_success else 0xEF4444  # Emerald or Red
    status_icon = "🟢" if is_success else "🔴"
    status_title = f"{status_icon} Sauvegarde {'Réussie' if is_success else 'Échouée'} : {log.job_name}"

    fields = [
        {"name": "🖥️ Serveur", "value": f"{log.server_name} (`{log.server_type}`)", "inline": True},
        {"name": "🗄️ Base / Dépôt", "value": f"`{log.database_name}`", "inline": True},
        {"name": "⏱️ Durée", "value": f"{log.duration_seconds or 0:.2f} s", "inline": True},
        {"name": "📦 Taille", "value": format_bytes(log.file_size_bytes), "inline": True},
        {"name": "📁 Emplacement", "value": f"`{log.file_path or 'N/A'}`", "inline": False},
    ]

    if log.error_message:
        # Limit error length in Discord embed
        err_truncated = log.error_message[:1000]
        fields.append({"name": "⚠️ Erreur", "value": f"```{err_truncated}```", "inline": False})

    payload = {
        "username": "Cronstash",
        "avatar_url": "https://raw.githubusercontent.com/favicon.ico",
        "embeds": [
            {
                "title": status_title,
                "color": embed_color,
                "fields": fields,
                "footer": {
                    "text": "Cronstash Backup System • Debian 13 (Trixie)"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(config.discord_webhook_url, json=payload)
            if resp.status_code in (200, 204):
                return True, "Notification Discord envoyée avec succès"
            else:
                return False, f"Discord Webhook a retourné le code {resp.status_code}: {resp.text[:200]}"
    except Exception as exc:
        logger.error(f"Failed to send Discord notification: {exc}")
        return False, f"Erreur de connexion Discord Webhook: {exc}"


async def test_smtp_configuration(config: NotificationConfig) -> Tuple[bool, str]:
    """Test SMTP connection and send a test message."""
    mock_log = BackupLog(
        job_name="Test de notification SMTP",
        server_name="test-server",
        server_type="postgresql",
        database_name="test_db",
        status="success",
        duration_seconds=1.23,
        file_size_bytes=1048576 * 42,
        file_path="/backup/cronstash/pgsql/test/test_db_20260930_120000.backup",
        error_message=None,
        started_at=datetime.now(timezone.utc)
    )
    return await send_smtp_notification(config, mock_log)


async def test_discord_configuration(webhook_url: str) -> Tuple[bool, str]:
    """Test Discord webhook by sending a mock test embed."""
    mock_config = NotificationConfig(
        discord_enabled=True,
        discord_webhook_url=webhook_url
    )
    mock_log = BackupLog(
        job_name="Test de notification Discord",
        server_name="test-srv",
        server_type="rdf4j",
        database_name="test-repo",
        status="success",
        duration_seconds=0.75,
        file_size_bytes=1048576 * 15,
        file_path="/backup/cronstash/rdf4j/test/test-repo_20260930_120000.ttl.gz",
        error_message=None,
        started_at=datetime.now(timezone.utc)
    )
    return await send_discord_notification(mock_config, mock_log)


async def dispatch_notifications_for_log(config: NotificationConfig, log: BackupLog) -> None:
    """Dispatches notifications according to user notification settings."""
    is_success = log.status == "success"
    should_send = (is_success and config.notify_on_success) or (not is_success and config.notify_on_failure)

    if not should_send:
        return

    tasks = []
    if config.smtp_enabled and config.smtp_host and config.smtp_to:
        tasks.append(send_smtp_notification(config, log))
    if config.discord_enabled and config.discord_webhook_url:
        tasks.append(send_discord_notification(config, log))

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
