import asyncio
import logging
from contextlib import asynccontextmanager

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
from conversion_service.app.portfolio_reports.router import router as portfolio_reports_router
from conversion_service.config.settings import settings

logger: logging.Logger = logging.getLogger(__name__)

# WinError 10022 ("invalid argument") from
# _ProactorBasePipeTransport._call_connection_lost is a known benign asyncio
# issue on Windows: the transport tries to shutdown a socket that the peer
# already closed. Suppress only this error so it does not pollute the log.
_PROACTOR_BENIGN_WINERROR: int = 10022


def _install_proactor_error_filter(loop: asyncio.AbstractEventLoop) -> None:
    """Игнорирует безвредный WinError 10022 при закрытии соединения на Windows."""
    previous_handler = loop.get_exception_handler()

    def _handler(
        current_loop: asyncio.AbstractEventLoop, context: dict
    ) -> None:
        exc = context.get("exception")
        if (
            isinstance(exc, OSError)
            and getattr(exc, "winerror", None) == _PROACTOR_BENIGN_WINERROR
        ):
            logger.debug("Ignored benign asyncio socket shutdown error: %s", exc)
            return
        if previous_handler is not None:
            previous_handler(current_loop, context)
        else:
            current_loop.default_exception_handler(context)

    loop.set_exception_handler(_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown hooks for the conversion service."""
    _install_proactor_error_filter(asyncio.get_running_loop())
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
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
    app.include_router(portfolio_reports_router, prefix=settings.API_V1_STR)

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
