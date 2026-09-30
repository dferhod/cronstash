import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.core.config import settings
from app.core.database import init_db, AsyncSessionLocal
from app.models.models import Job
from app.services.crontab import sync_system_crontab
from app.api import auth, dashboard, servers, jobs, backups, logs, notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure DB and folders are initialized
    settings.effective_backup_path
    settings.effective_db_path
    await init_db()

    # Synchronize crontab on service startup
    async with AsyncSessionLocal() as session:
        res = await session.execute(select(Job))
        existing_jobs = res.scalars().all()
        sync_system_crontab(list(existing_jobs))

    yield

    # Shutdown logic if needed
    pass


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Gestionnaire de sauvegardes automatiques pour PostgreSQL 18 et RDF4J",
    lifespan=lifespan
)

# CORS configuration
origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(auth.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(servers.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(backups.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")


@app.get("/api/health", tags=["Système"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "db": str(settings.effective_db_path),
        "backups": str(settings.effective_backup_path)
    }


# Static Frontend SPA Serving (Debian build or local build)
frontend_build_paths = [
    Path(settings.APP_ROOT) / "frontend" / "build",
    Path("./frontend/build").resolve(),
    Path("../frontend/build").resolve()
]

frontend_dir: Path | None = None
for p in frontend_build_paths:
    if p.exists() and (p / "index.html").exists():
        frontend_dir = p
        break

if frontend_dir:
    # Mount static assets
    if (frontend_dir / "_app").exists():
        app.mount("/_app", StaticFiles(directory=str(frontend_dir / "_app")), name="app_assets")

    @app.get("/", include_in_schema=False)
    async def serve_spa_root():
        index_path = frontend_dir / "index.html"
        return FileResponse(index_path)

    # SPA catch-all for client-side routing
    @app.middleware("http")
    async def spa_middleware(request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 404 and not request.url.path.startswith("/api/"):
            index_path = frontend_dir / "index.html"
            if index_path.exists():
                return FileResponse(index_path)
        return response
