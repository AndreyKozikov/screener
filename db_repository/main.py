import sys
from pathlib import Path
from db_repository.core.database_init import init_database
from db_repository.config.paths import DB_PATH
from contextlib import asynccontextmanager

# Add the project root to sys.path to allow imports like 'db_repository.routers'
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_database(DB_PATH)
    yield

app = FastAPI(lifespan=lifespan)

from db_repository.routers.bond_router import bond_router
from db_repository.routers.ratings_router import ratings_router
from db_repository.routers.coupon_router import coupon_router
from db_repository.routers.emitent_router import emitent_router

app.include_router(bond_router)
app.include_router(ratings_router)
app.include_router(coupon_router)
app.include_router(emitent_router)


if __name__ == "__main__":
    # Репозиторий базы данных
    import uvicorn
    import multiprocessing

    # Для production используйте Gunicorn с несколькими workers:
    # gunicorn -c config/gunicorn_config.py main:app
    #
    # Для разработки можно использовать uvicorn напрямую,
    # но лучше указать workers для тестирования параллельной обработки
    workers = multiprocessing.cpu_count() * 2 + 1

    uvicorn.run(
        "db_repository.main:app",
        host="0.0.0.0",  # Listen on all interfaces for external access
        port=8964,
        reload=True,  # Только для разработки
        workers=1,  # В режиме reload workers должен быть 1
        # Для production без reload используйте:
        # workers=workers,
    )