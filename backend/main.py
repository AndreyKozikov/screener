from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import bonds, metadata, zerocupon, forecast, llm, qwen, grok
from app.services.data_loader import init_data_loader
from app.services.coupon_loader import init_coupon_loader
from app.config import settings


# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize data loaders
    data_dir = Path(__file__).parent / "app" / "data"
    init_data_loader(data_dir)
    init_coupon_loader(data_dir)
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
    uvicorn.run(
        "main:app",
        host="0.0.0.0",  # Listen on all interfaces for external access
        port=8000,
        reload=True,
    )
