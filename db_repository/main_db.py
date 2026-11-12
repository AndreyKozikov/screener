import sqlite3
import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Add the project root to sys.path to allow imports like 'db_repository.routers'
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from db_repository.config.paths import (
    BLOG_DB_PATH,
    DB_PATH,
    HISTORY_DB_PATH,
    PORTFOLIO_DB_PATH,
)
from db_repository.config.settings import settings
from db_repository.core.database_init import init_database
from db_repository.core.migrations import (
    run_blog_migrations,
    run_history_migrations,
    run_migrations,
    run_portfolio_migrations,
)
from db_repository.core.portfolio_database_init import init_portfolio_database
from db_repository.core.security import is_authorized


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.run_migrations_on_startup:
        run_migrations()
        run_blog_migrations()
        run_history_migrations()
        run_portfolio_migrations()
    init_database(DB_PATH)
    init_portfolio_database(PORTFOLIO_DB_PATH)
    yield


app = FastAPI(
    title="BondsScreener database repository",
    lifespan=lifespan,
)


@app.middleware("http")
async def api_key_middleware(request, call_next):
    """Защитить все межсервисные и служебные маршруты, кроме /health."""
    path = request.url.path
    protected = (
        path.startswith("/api")
        or path.startswith("/internal")
        or path in {"/ready", "/docs", "/redoc", "/openapi.json"}
    )
    if protected and not is_authorized(request.headers.get("X-API-Key")):
        if settings.require_api_key and not settings.api_key.get_secret_value():
            return JSONResponse(
                status_code=503,
                content={"detail": "API key is not configured for the database service"},
            )
        return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
    return await call_next(request)


def _database_check(name: str, path: Path) -> tuple[bool, str]:
    if not path.is_file():
        return False, f"{name} database file is missing: {path}"
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
            row = connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name = 'alembic_version'"
            ).fetchone()
            if row is None:
                return False, f"{name} database has no alembic_version table"
            version = connection.execute(
                "SELECT version_num FROM alembic_version"
            ).fetchone()
            if version is None:
                return False, f"{name} database has no applied migration version"
    except sqlite3.Error as exc:
        return False, f"{name} database is not readable: {exc}"
    return True, ""


@app.get("/health")
async def health_check():
    """Liveness probe: не требует ключа и не обращается к БД."""
    return {"status": "healthy"}


@app.get("/ready")
async def readiness_check():
    """Readiness probe: проверяет файлы БД и применённые миграции."""
    checks = {
        "bonds": DB_PATH,
        "blog": BLOG_DB_PATH,
        "history": HISTORY_DB_PATH,
        "portfolios": PORTFOLIO_DB_PATH,
    }
    errors = [
        detail
        for name, path in checks.items()
        for ok, detail in [_database_check(name, path)]
        if not ok
    ]
    if errors:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "errors": errors},
        )
    return {"status": "ready"}


from db_repository.routers.bond_router import bond_router
from db_repository.routers.ratings_router import ratings_router
from db_repository.routers.coupon_router import coupon_router
from db_repository.routers.emitent_router import emitent_router
from db_repository.routers.inflations_router import inflation_router
from db_repository.routers.ipc_router import ipc_router
from db_repository.routers.repository_rpc_router import repository_rpc_router

app.include_router(bond_router)
app.include_router(ratings_router)
app.include_router(coupon_router)
app.include_router(emitent_router)
app.include_router(inflation_router)
app.include_router(ipc_router)
app.include_router(repository_rpc_router)

