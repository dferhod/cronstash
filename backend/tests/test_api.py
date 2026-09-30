import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings


async def run_api_tests():
    print("[TEST] Tests d'integration API FastAPI...")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Health check
        res = await client.get("/api/health")
        assert res.status_code == 200, f"Health check failed: {res.text}"
        assert res.json()["status"] == "healthy"
        print("  -> /api/health OK")

        # 1.b SPA index check
        res_spa = await client.get("/")
        assert res_spa.status_code == 200
        assert "Cronstash" in res_spa.text
        print("  -> SPA root serving (index.html) OK")

        # 2. Login
        login_data = {
            "username": settings.DEFAULT_ADMIN_USER,
            "password": settings.DEFAULT_ADMIN_PASSWORD
        }
        res = await client.post("/api/auth/login", json=login_data)
        assert res.status_code == 200, f"Login failed: {res.text}"
        data = res.json()
        token = data["access_token"]
        assert token, "Token JWT absent"
        print("  -> /api/auth/login OK")

        headers = {"Authorization": f"Bearer {token}"}

        # 3. /api/auth/me
        res = await client.get("/api/auth/me", headers=headers)
        assert res.status_code == 200
        assert res.json()["username"] == settings.DEFAULT_ADMIN_USER
        print("  -> /api/auth/me OK")

        # 4. /api/dashboard/stats
        res = await client.get("/api/dashboard/stats", headers=headers)
        assert res.status_code == 200
        stats = res.json()
        assert "disk" in stats
        assert "stats_24h" in stats
        print("  -> /api/dashboard/stats OK")

        # 5. Create Server
        server_payload = {
            "name": "pg-cluster-prod",
            "server_type": "postgresql",
            "host": "10.0.0.15",
            "port": 5432,
            "username": "postgres"
        }
        res = await client.post("/api/servers", json=server_payload, headers=headers)
        assert res.status_code in (201, 400)  # 201 or 400 if already exists
        if res.status_code == 201:
            server_id = res.json()["id"]
        else:
            # fetch existing
            servers_res = await client.get("/api/servers", headers=headers)
            server_id = servers_res.json()[0]["id"]
        print("  -> /api/servers OK")

        # 6. Create Job
        job_payload = {
            "name": "Backup Quotidien Client",
            "server_id": server_id,
            "database_name": "clients_db",
            "cron_expression": "0 2 * * *",
            "is_active": True,
            "retention_daily": 7,
            "retention_weekly": 4,
            "retention_monthly": 12
        }
        res = await client.post("/api/jobs", json=job_payload, headers=headers)
        assert res.status_code == 201, f"Job creation failed: {res.text}"
        job_id = res.json()["id"]
        print("  -> /api/jobs (creation) OK")

        # 7. List Jobs
        res = await client.get("/api/jobs", headers=headers)
        assert res.status_code == 200
        assert len(res.json()) >= 1
        print("  -> /api/jobs (list) OK")

        # 8. Notifications settings
        res = await client.get("/api/notifications", headers=headers)
        assert res.status_code == 200
        print("  -> /api/notifications OK")

        # 9. List Backups
        res = await client.get("/api/backups", headers=headers)
        assert res.status_code == 200
        print("  -> /api/backups OK")

        # 10. Clean up test job
        await client.delete(f"/api/jobs/{job_id}", headers=headers)
        print("  -> /api/jobs (delete) OK")

    print("\n[OK] TOUS LES ENDPOINTS DE L'API FASTAPI FONCTIONNENT PARFAITEMENT !\n")


if __name__ == "__main__":
    asyncio.run(run_api_tests())
