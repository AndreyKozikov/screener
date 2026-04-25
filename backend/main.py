import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import bonds, metadata, zerocupon, forecast, llm, qwen, grok, emitent, rating, feedback, currency, ruonia, keyrate, dashboard, trading_history, edisclosure, pipeline
from app.services.data_loader import init_data_loader
from app.services.emitent_service import init_emitent_service
from app.services.currency_service import init_currency_service
from app.services.ruonia_service import init_ruonia_service
from app.services.keyrate_service import init_keyrate_service
from app.services.trading_history_service import init_trading_history_service
from app.services.kbd_service import init_kbd_service
from config.settings import settings
from app.core.database_init import run_migrations
from app.repository.db.emitents_repository import EmitentsRepository
from config.paths import DATA_DIR, DB_PATH


# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Apply Alembic migrations (bonds table structure)
    print("[STARTUP] run_migrations start", flush=True)
    run_migrations()
    print("[STARTUP] run_migrations done", flush=True)
    # Startup: Initialize data loaders
    print("[STARTUP] init_data_loader start", flush=True)
    init_data_loader(DATA_DIR)
    print("[STARTUP] init_data_loader done", flush=True)
    print("[STARTUP] init_emitent_service start", flush=True)
    emitents_repo = EmitentsRepository(db_path=DB_PATH, data_dir=DATA_DIR)
    init_emitent_service(DATA_DIR, emitents_repository=emitents_repo)
    print("[STARTUP] init_emitent_service done", flush=True)
    print("[STARTUP] init_currency_service start", flush=True)
    init_currency_service()
    print("[STARTUP] init_currency_service done", flush=True)
    print("[STARTUP] init_ruonia_service start", flush=True)
    init_ruonia_service(DATA_DIR)
    print("[STARTUP] init_ruonia_service done", flush=True)
    print("[STARTUP] init_keyrate_service start", flush=True)
    init_keyrate_service()
    print("[STARTUP] init_keyrate_service done", flush=True)
    print("[STARTUP] init_trading_history_service start", flush=True)
    init_trading_history_service(DATA_DIR)
    print("[STARTUP] init_trading_history_service done", flush=True)
    # Initialize KBD service (uses database, not data_dir)
    print("[STARTUP] init_kbd_service start", flush=True)
    init_kbd_service()
    print("[STARTUP] init_kbd_service done", flush=True)
    print("[STARTUP] Application startup complete", flush=True)
    yield
    # Shutdown: cleanup if needed
    # (currently no cleanup required)


# Initialize FastAPI app
app = FastAPI(
    title="Bonds Screener API",
    description="Moscow Exchange Bonds Screener API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(bonds.router)
app.include_router(metadata.router)
app.include_router(zerocupon.router)
app.include_router(forecast.router)
app.include_router(llm.router)
app.include_router(qwen.router)
app.include_router(grok.router)
app.include_router(emitent.router)
app.include_router(rating.router)
app.include_router(feedback.router)
app.include_router(currency.router)
app.include_router(ruonia.router)
app.include_router(keyrate.router)
app.include_router(dashboard.router)
app.include_router(trading_history.router)
app.include_router(edisclosure.router)
app.include_router(pipeline.router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Bonds Screener API",
        "version": "1.0.0",
        "description": "Moscow Exchange Bonds Screener API",
        "endpoints": {
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "bonds": "/api/bonds",
            "bond_detail": "/api/bonds/{secid}",
            "columns": "/api/columns",
            "descriptions": "/api/descriptions",
            "filter_options": "/api/filter-options"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    import multiprocessing
    
    # Для production используйте Gunicorn с несколькими workers:
    # gunicorn -c config/gunicorn_config.py main:app
    #
    # Для разработки можно использовать uvicorn напрямую,
    # но лучше указать workers для тестирования параллельной обработки
    workers = multiprocessing.cpu_count() * 2 + 1
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Listen on all interfaces for external access
        port=8000,
        reload=True,  # Только для разработки
        workers=1,  # В режиме reload workers должен быть 1
        # Для production без reload используйте:
        # workers=workers,
    )
