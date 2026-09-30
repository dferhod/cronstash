import asyncio
import os
import sys
import shutil
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Insert backend directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.services.gfs import BackupFileInfo, calculate_gfs_retention, apply_gfs_purge
from app.services.crontab import generate_cron_content
from app.models.models import Server, Job, BackupLog, User, NotificationConfig
from sqlalchemy import select


def test_security():
    print("[TEST] Sécurité Argon2id et JWT...")
    pwd = "MySecretPassword123!"
    h = hash_password(pwd)
    assert h.startswith("$argon2id$"), "Hash doit être Argon2id"
    assert verify_password(pwd, h), "Le mot de passe doit être vérifié"
    assert not verify_password("WrongPassword", h), "Faux mot de passe doit être rejeté"

    token = create_access_token(subject="1")
    payload = decode_access_token(token)
    assert payload is not None and payload["sub"] == "1", "JWT token doit être valide"
    print("  -> Sécurité OK")


def test_gfs_algorithm():
    print("[TEST] Algorithme GFS (Grandfather-Father-Son)...")
    test_dir = Path("./data/test_gfs").resolve()
    test_dir.mkdir(parents=True, exist_ok=True)

    # Clean test directory
    for f in test_dir.iterdir():
        if f.is_file():
            f.unlink()

    # Generate 45 days of simulated backup files
    # DB name: "app_db"
    base_time = datetime(2026, 9, 30, 2, 0, 0, tzinfo=timezone.utc)
    created_files = []
    for day_offset in range(45):
        dt = base_time - timedelta(days=day_offset)
        ts_str = dt.strftime("%Y%m%d_%H%M%S")
        fpath = test_dir / f"app_db_{ts_str}.backup"
        fpath.write_text(f"dummy backup content for day {day_offset}")
        created_files.append(fpath)

    # Apply GFS: N1=7 (daily), N2=4 (weekly), N3=3 (monthly)
    result = apply_gfs_purge(
        target_dir=test_dir,
        database_name="app_db",
        n1_daily=7,
        n2_weekly=4,
        n3_monthly=3
    )

    retained_count = result["retained_count"]
    purged_count = result["purged_count"]
    print(f"  -> Total créés: 45 | Conservés: {retained_count} | Purgés: {purged_count}")
    assert retained_count <= (7 + 4 + 3), "Le nombre conservé doit respecter les quotas"
    assert purged_count > 0, "Les fichiers anciens hors politique doivent être purgés"
    assert retained_count + purged_count == 45, "Tous les fichiers doivent être classés"

    # Cleanup test dir
    shutil.rmtree(test_dir, ignore_errors=True)
    print("  -> Algorithme GFS OK")


def test_crontab_generation():
    print("[TEST] Génération du fichier crontab /etc/cron.d/cronstash...")
    job1 = Job(
        id=1,
        name="Backup PG Prod",
        database_name="production_db",
        cron_expression="0 2 * * *",
        is_active=True
    )
    job2 = Job(
        id=2,
        name="Backup RDF4J KG",
        database_name="knowledge_graph",
        cron_expression="30 3 * * 0",
        is_active=True
    )
    job3 = Job(
        id=3,
        name="Job Inactif",
        database_name="old_db",
        cron_expression="0 1 * * *",
        is_active=False
    )

    content = generate_cron_content([job1, job2, job3])
    assert "SHELL=/bin/bash" in content
    assert "PATH=/usr/local/sbin" in content
    assert "Job ID 1" in content
    assert "Job ID 2" in content
    assert "Job ID 3" not in content  # Job inactif ignoré
    assert "0 2 * * * root" in content
    assert "run-job --id 1" in content
    print("  -> Crontab OK")


async def async_tests():
    await init_db()
    async with AsyncSessionLocal() as session:
        # Check Admin exists
        res = await session.execute(select(User))
        users = res.scalars().all()
        assert len(users) >= 1, "Un compte admin doit être présent"

        # Check default Notification config
        n_res = await session.execute(select(NotificationConfig))
        cfg = n_res.scalar_one_or_none()
        assert cfg is not None, "Config notification doit être créée"

        print("  -> Base SQLite asynchrone OK")


def run_all():
    test_security()
    test_gfs_algorithm()
    test_crontab_generation()
    asyncio.run(async_tests())
    print("\n[OK] TOUS LES TESTS UNITAIRES DU BACKEND SONT VALIDES AVEC SUCCES !\n")


if __name__ == "__main__":
    run_all()
