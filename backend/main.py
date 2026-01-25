from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import bonds, metadata, zerocupon, forecast, llm, qwen, grok, emitent, rating, feedback, currency, ruonia, keyrate, trading_history
from app.services.data_loader import init_data_loader
from app.services.coupon_loader import init_coupon_loader
from app.services.emitent_service import init_emitent_service
from app.services.rating_service import init_rating_service
from app.services.currency_service import init_currency_service
from app.services.ruonia_service import init_ruonia_service
from app.services.keyrate_service import init_keyrate_service
from app.services.trading_history_service import init_trading_history_service
from app.config import settings


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize data loaders
    data_dir = Path(__file__).parent / "app" / "data"
    init_data_loader(data_dir)
    init_coupon_loader(data_dir)
    init_emitent_service(data_dir)
    init_rating_service(data_dir)
    init_currency_service(data_dir)
    init_ruonia_service(data_dir)
    init_keyrate_service(data_dir)
    init_trading_history_service(data_dir)
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
app.include_router(trading_history.router)

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
    # gunicorn -c gunicorn_config.py main:app
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
