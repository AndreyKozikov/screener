"""Создание HTTP-приложения и управление ресурсами микросервиса."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from .config.settings import Settings
from .http_utils import error
from .offline_embeddings import LocalBGE
from .repository.vector_store import VectorStore
from .routers import health, ingestion, search
from .services.document_index import DocumentIndex


@asynccontextmanager
async def lifespan(app):
    settings = Settings()
    encoder = LocalBGE(settings.model_dir)
    store = VectorStore(settings.db_dir, settings.embedding_dim, settings.model_id,
                        settings.sparse_source, ttl=settings.gc_timeout)
    app.state.index = DocumentIndex(store, encoder)
    app.state.key = settings.service_api_key.get_secret_value()
    try:
        yield
    finally:
        store.close()


app = FastAPI(lifespan=lifespan)
app.include_router(ingestion.router)
app.include_router(search.router)
app.include_router(health.router)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    return error(400, "invalid_request", str(exc))


@app.exception_handler(Exception)
async def internal_error(request: Request, exc: Exception):
    logging.getLogger(__name__).error("Ошибка обработки %s", request.url.path, exc_info=exc)
    return error(500, "internal_error", "Не удалось завершить обработку запроса")
