import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import (
    bonds, metadata, zerocupon, forecast, emitent, rating, currency, ruonia, keyrate,
    feedback, dashboard,
    llm_router, blog, inflations, ipc, settings as settings_router,
    portfolio, auth, portfolio_reports
)

from app.services.data_loader import init_data_loader
from app.services.emitent_service import init_emitent_service
from app.services.kbd_service import init_kbd_service
from config.settings import settings
from app.repository.db.emitents_repository import EmitentsRepository
from config.paths import DATA_DIR, EMITENT_EVENTS_JSON_DIR
from app.core.exception_handlers import register_pipeline_exception_handlers
from app.repository.db import init_bonds_repository, init_history_repository, init_bond_float_repository
from app.repository.files import init_markdownfile_repository, init_file_storage
from app.processors import init_events_processor, init_bond_llm_processor
from app.services.vector_retrieval import init_retrieval_pipeline
from app.services import init_llm_provider_resolution_service, init_llm_analysis_service, init_runtime_settings
from app.agent import router as agent_router
from app.macro_dashboard.router import router as macro_dashboard_router
from app.services.auth_service import validate_auth_configuration

# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s:     %(message)s",
)
logger = logging.getLogger(__name__)


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: apply runtime settings overrides before services initialize
    print("[STARTUP] init_runtime_settings start", flush=True)
    init_runtime_settings()
    print("[STARTUP] init_runtime_settings done", flush=True)
    validate_auth_configuration()
    print("[STARTUP] AUTH_SECRET_KEY loaded from backend/.env", flush=True)
    # Startup: Initialize data loaders
    print("[STARTUP] init_data_loader start", flush=True)
    init_data_loader(DATA_DIR)
    print("[STARTUP] init_data_loader done", flush=True)
    print("[STARTUP] init_emitent_service start", flush=True)
    emitents_repo = EmitentsRepository()
    init_emitent_service(DATA_DIR, emitents_repository=emitents_repo)
    print("[STARTUP] init_emitent_service done", flush=True)
    # Initialize KBD service (uses database, not data_dir)
    print("[STARTUP] init_kbd_service start", flush=True)
    init_kbd_service()
    print("[STARTUP] init_kbd_service done", flush=True)
    init_bonds_repository()
    init_bond_float_repository()
    print("[STARTUP] init_bonds_repository done", flush=True)
    init_history_repository()
    print("[STARTUP] init_history_repository done", flush=True)
    init_markdownfile_repository(DATA_DIR)
    init_events_processor(EMITENT_EVENTS_JSON_DIR)
    init_bond_llm_processor(DATA_DIR)
    init_file_storage()
    init_retrieval_pipeline()
    init_llm_provider_resolution_service()
    init_llm_analysis_service()
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

register_pipeline_exception_handlers(app)

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
app.include_router(llm_router.router)
app.include_router(emitent.router)
app.include_router(rating.router)
app.include_router(currency.router)
app.include_router(ruonia.router)
app.include_router(keyrate.router)
app.include_router(feedback.router)
app.include_router(dashboard.router)
#app.include_router(llm_float_analize_param.router)
#app.include_router(vector_retrieval.router)
if settings.AGENT_ENABLED:
    app.include_router(agent_router.router)
app.include_router(blog.public_router)
app.include_router(blog.admin_router)
app.include_router(inflations.inflation_router)
app.include_router(ipc.ipc_router)
app.include_router(settings_router.router)
app.include_router(macro_dashboard_router)
app.include_router(portfolio.router)
app.include_router(portfolio_reports.router)
app.include_router(auth.router)

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
            "portfolio_report_import": "/api/portfolios/import",
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
