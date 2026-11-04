import uvicorn

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from conversion_service.app.routers import (
    emission_doc_download,
    edisclosure_events,
    bonds_router,
    emitents_router,
    ipc_router,
    inflation_router,
)
from conversion_service.app.routers.market_data_router import (
    coupons_router,
    currency_router,
    keyrate_router,
    rating_router,
    ruonia_router,
    trading_history_router,
    zerocupon_router,
)
from conversion_service.app.routers import event_processing_router, edisclosure_update_router
from conversion_service.app.routers import forecast_router
from config.settings import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
    )

    if settings.CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(
        emission_doc_download.router,
        prefix=settings.API_V1_STR,
    )
    app.include_router(
        edisclosure_events.router,
        prefix=settings.API_V1_STR,
    )
    app.include_router(event_processing_router.router, prefix=settings.API_V1_STR)
    app.include_router(edisclosure_update_router.router, prefix=settings.API_V1_STR)
    app.include_router(forecast_router.router, prefix=settings.API_V1_STR)

    app.include_router(
        bonds_router.router,
        prefix=settings.API_V1_STR,
    )

    app.include_router(
        emitents_router.router,
        prefix=settings.API_V1_STR,
    )

    app.include_router(
        ipc_router.router,
        prefix=settings.API_V1_STR,
    )

    app.include_router(
        inflation_router.router,
        prefix=settings.API_V1_STR,
    )

    for router in (
        coupons_router,
        currency_router,
        keyrate_router,
        rating_router,
        ruonia_router,
        trading_history_router,
        zerocupon_router,
    ):
        app.include_router(router, prefix=settings.API_V1_STR)

    return app


app = create_app()

#Микросервис обновления данных
if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=12345,
        reload=False,
        workers=1,
        log_level="info",
        access_log=True,
    )
