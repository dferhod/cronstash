from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.models import Server, Job, User
from app.schemas.schemas import ServerCreate, ServerUpdate, ServerOut, ServerDiscoveryResponse, DiscoveredDatabase
from app.api.deps import get_current_user
from app.services.discovery import discover_server_databases
from app.services.crontab import sync_system_crontab

router = APIRouter(prefix="/servers", tags=["Serveurs"])


@router.get("", response_model=List[ServerOut])
async def list_servers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """List all registered servers."""
    result = await db.execute(select(Server).order_by(Server.name))
    servers = result.scalars().all()
    out = []
    for s in servers:
        s_out = ServerOut(
            id=s.id,
            name=s.name,
            server_type=s.server_type,
            host=s.host,
            port=s.port,
            username=s.username,
            extra_params=s.extra_params,
            has_password=bool(s.password),
            created_at=s.created_at,
            updated_at=s.updated_at
        )
        out.append(s_out)
    return out


@router.post("", response_model=ServerOut, status_code=status.HTTP_201_CREATED)
async def create_server(
    payload: ServerCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Register a new PostgreSQL or RDF4J server."""
    # Check uniqueness of name
    stmt = select(Server).where(Server.name == payload.name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Un serveur nommé '{payload.name}' existe déjà."
        )

    server = Server(
        name=payload.name,
        server_type=payload.server_type,
        host=payload.host,
        port=payload.port,
        username=payload.username,
        password=payload.password,
        extra_params=payload.extra_params
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)

    return ServerOut(
        id=server.id,
        name=server.name,
        server_type=server.server_type,
        host=server.host,
        port=server.port,
        username=server.username,
        extra_params=server.extra_params,
        has_password=bool(server.password),
        created_at=server.created_at,
        updated_at=server.updated_at
    )


@router.get("/{server_id}", response_model=ServerOut)
async def get_server(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve details for a specific server."""
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serveur introuvable")

    return ServerOut(
        id=server.id,
        name=server.name,
        server_type=server.server_type,
        host=server.host,
        port=server.port,
        username=server.username,
        extra_params=server.extra_params,
        has_password=bool(server.password),
        created_at=server.created_at,
        updated_at=server.updated_at
    )


@router.put("/{server_id}", response_model=ServerOut)
async def update_server(
    server_id: int,
    payload: ServerUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Update server configuration."""
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serveur introuvable")

    if payload.name is not None and payload.name != server.name:
        stmt = select(Server).where(Server.name == payload.name)
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Un serveur nommé '{payload.name}' existe déjà."
            )
        server.name = payload.name

    if payload.server_type is not None:
        server.server_type = payload.server_type
    if payload.host is not None:
        server.host = payload.host
    if payload.port is not None:
        server.port = payload.port
    if payload.username is not None:
        server.username = payload.username
    if payload.password is not None and payload.password != "":
        server.password = payload.password
    if payload.extra_params is not None:
        server.extra_params = payload.extra_params

    await db.commit()
    await db.refresh(server)

    return ServerOut(
        id=server.id,
        name=server.name,
        server_type=server.server_type,
        host=server.host,
        port=server.port,
        username=server.username,
        extra_params=server.extra_params,
        has_password=bool(server.password),
        created_at=server.created_at,
        updated_at=server.updated_at
    )


@router.delete("/{server_id}")
async def delete_server(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a server and synchronize crontab for any cascaded jobs."""
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serveur introuvable")

    await db.delete(server)
    await db.commit()

    # Re-sync crontab
    all_jobs_res = await db.execute(select(Job))
    all_jobs = all_jobs_res.scalars().all()
    sync_system_crontab(list(all_jobs))

    return {"message": f"Serveur '{server.name}' supprimé avec succès"}


@router.post("/{server_id}/discover", response_model=ServerDiscoveryResponse)
async def discover_databases(
    server_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Connect to PostgreSQL (excluding template and postgres) or RDF4J
    and return list of available databases / repositories with monitoring status.
    """
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Serveur introuvable")

    try:
        raw_databases = await discover_server_databases(server)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Échec de la découverte des bases : {exc}"
        )

    # Check which databases already have a job configured on this server
    existing_jobs_res = await db.execute(
        select(Job.database_name).where(Job.server_id == server.id)
    )
    monitored_names = set(existing_jobs_res.scalars().all())

    annotated_dbs: List[DiscoveredDatabase] = []
    for d in raw_databases:
        annotated_dbs.append(
            DiscoveredDatabase(
                name=d.name,
                title=d.title,
                size_formatted=d.size_formatted,
                already_monitored=(d.name in monitored_names)
            )
        )

    return ServerDiscoveryResponse(
        server_id=server.id,
        server_name=server.name,
        server_type=server.server_type,
        databases=annotated_dbs
    )
