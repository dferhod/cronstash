import asyncio
import logging
from typing import List, Dict, Any, Optional
import httpx
from app.models.models import Server
from app.schemas.schemas import DiscoveredDatabase

logger = logging.getLogger("cronstash.discovery")


async def discover_postgresql_databases(
    host: str,
    port: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    extra_params: Optional[str] = None,
    timeout: float = 10.0
) -> List[DiscoveredDatabase]:
    """
    Connect to PostgreSQL and query all non-template databases (excluding 'postgres').
    SELECT datname FROM pg_database WHERE datistemplate = false AND datname != 'postgres';
    """
    databases: List[DiscoveredDatabase] = []
    
    # Try using asyncpg if available
    try:
        import asyncpg
        conn = await asyncio.wait_for(
            asyncpg.connect(
                host=host,
                port=port,
                user=username or "postgres",
                password=password or "",
                database="postgres",
                timeout=timeout
            ),
            timeout=timeout
        )
        try:
            rows = await conn.fetch(
                """
                SELECT datname, pg_size_pretty(pg_database_size(datname)) as size_str 
                FROM pg_database 
                WHERE datistemplate = false AND datname != 'postgres'
                ORDER BY datname;
                """
            )
            for row in rows:
                databases.append(
                    DiscoveredDatabase(
                        name=row["datname"],
                        title=f"Base PostgreSQL: {row['datname']}",
                        size_formatted=row.get("size_str")
                    )
                )
        finally:
            await conn.close()
        return databases
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"asyncpg discovery failed: {e}. Trying psycopg fallback...")

    # Fallback to psycopg (version 3)
    try:
        import psycopg
        conn_str = f"host={host} port={port} dbname=postgres user={username or 'postgres'}"
        if password:
            conn_str += f" password={password}"
        conn_str += f" connect_timeout={int(timeout)}"

        def _sync_query():
            with psycopg.connect(conn_str) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT datname, pg_size_pretty(pg_database_size(datname)) 
                        FROM pg_database 
                        WHERE datistemplate = false AND datname != 'postgres'
                        ORDER BY datname;
                        """
                    )
                    return cur.fetchall()

        rows = await asyncio.to_thread(_sync_query)
        for row in rows:
            databases.append(
                DiscoveredDatabase(
                    name=row[0],
                    title=f"Base PostgreSQL: {row[0]}",
                    size_formatted=str(row[1]) if len(row) > 1 else None
                )
            )
        return databases
    except Exception as exc:
        logger.error(f"PostgreSQL discovery failed on {host}:{port} - {exc}")
        raise RuntimeError(f"Impossible de joindre le serveur PostgreSQL ({host}:{port}): {exc}")


async def discover_rdf4j_repositories(
    host: str,
    port: int,
    username: Optional[str] = None,
    password: Optional[str] = None,
    extra_params: Optional[str] = None,
    timeout: float = 10.0
) -> List[DiscoveredDatabase]:
    """
    Query RDF4J Server via HTTP GET <rdf4j_url>/repositories with Accept: application/json
    Parses repositories (id, title, readable, writable).
    """
    databases: List[DiscoveredDatabase] = []
    
    # Construct base URL (handling schemes)
    if host.startswith("http://") or host.startswith("https://"):
        base_url = host
    else:
        scheme = "https" if port == 443 else "http"
        base_url = f"{scheme}://{host}:{port}"

    # Handle path in host if user provided full path like http://server:8080/rdf4j-server
    if not base_url.endswith("/repositories"):
        if "/rdf4j-server" not in base_url and not base_url.endswith("/"):
            # Check if extra_params specifies prefix or check default /rdf4j-server
            target_url = f"{base_url}/repositories"
        else:
            target_url = f"{base_url.rstrip('/')}/repositories"
    else:
        target_url = base_url

    headers = {
        "Accept": "application/json"
    }

    auth = None
    if username and password:
        auth = (username, password)

    async with httpx.AsyncClient(timeout=timeout, verify=False) as client:
        try:
            resp = await client.get(target_url, headers=headers, auth=auth)
            
            # If 404, maybe it needs /rdf4j-server/repositories
            if resp.status_code == 404 and "/rdf4j-server" not in target_url:
                target_url_fallback = f"{base_url.rstrip('/')}/rdf4j-server/repositories"
                resp = await client.get(target_url_fallback, headers=headers, auth=auth)

            resp.raise_for_status()
            data = resp.json()

            # RDF4J SPARQL JSON format typically has:
            # { "results": { "bindings": [ { "id": { "value": "repo1" }, "title": { "value": "..." } } ] } }
            # or direct JSON list if custom API: [ {"id": "repo1", "title": "..."} ]
            if isinstance(data, dict) and "results" in data and "bindings" in data["results"]:
                for binding in data["results"]["bindings"]:
                    repo_id = binding.get("id", {}).get("value", "")
                    title = binding.get("title", {}).get("value", "")
                    readable = binding.get("readable", {}).get("value", "true") == "true"
                    if repo_id:
                        databases.append(
                            DiscoveredDatabase(
                                name=repo_id,
                                title=title or f"RDF4J Repository: {repo_id}",
                                size_formatted="Lecture: " + ("Oui" if readable else "Non")
                            )
                        )
            elif isinstance(data, list):
                for item in data:
                    repo_id = item.get("id")
                    title = item.get("title", "")
                    if repo_id:
                        databases.append(
                            DiscoveredDatabase(
                                name=repo_id,
                                title=title or f"RDF4J Repository: {repo_id}",
                                size_formatted=None
                            )
                        )
            else:
                logger.warning(f"Unexpected RDF4J response format from {target_url}: {data}")

            return databases

        except httpx.HTTPStatusError as e:
            logger.error(f"RDF4J HTTP error {e.response.status_code} at {target_url}")
            raise RuntimeError(f"Erreur HTTP RDF4J ({e.response.status_code}): {e.response.text[:200]}")
        except httpx.RequestError as e:
            logger.error(f"RDF4J connection failed to {target_url}: {e}")
            raise RuntimeError(f"Impossible de joindre le serveur RDF4J ({target_url}): {e}")


async def discover_server_databases(server: Server) -> List[DiscoveredDatabase]:
    """Helper dispatcher based on server type."""
    if server.server_type == "postgresql":
        return await discover_postgresql_databases(
            host=server.host,
            port=server.port,
            username=server.username,
            password=server.password,
            extra_params=server.extra_params
        )
    elif server.server_type == "rdf4j":
        return await discover_rdf4j_repositories(
            host=server.host,
            port=server.port,
            username=server.username,
            password=server.password,
            extra_params=server.extra_params
        )
    else:
        raise ValueError(f"Type de serveur inconnu: {server.server_type}")
