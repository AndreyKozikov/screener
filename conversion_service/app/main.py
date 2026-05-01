import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import emission_doc_download

# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s: %(message)s",
    force=True,
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[STARTUP] Микросервис конвертации запущен и готов к приему запросов.")
    yield
    logger.info("[SHUTDOWN] Микросервис конвертации остановлен.")

app = FastAPI(
    title="Conversion Service",
    description="Emission document download and conversion service",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(emission_doc_download.router)

@app.get("/health")
async def health():
    return {"status": "ok"}
