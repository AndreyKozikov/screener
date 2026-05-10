from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import emission_doc_download, edisclosure_events
from config.settings import settings

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
    )

    # Настройка CORS
    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Регистрация роутеров
    app.include_router(
        emission_doc_download.router,
        prefix=settings.API_V1_STR
    )
    app.include_router(
        edisclosure_events.router,
        prefix=settings.API_V1_STR
    )

    return app

app = create_app()
