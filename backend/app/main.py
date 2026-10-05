from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import settings
from app.core.db import init_database
from app.services.engine import engine_service
import app.core.models  # noqa: F401  (register SQLAlchemy models before DB init)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Neither dependency is allowed to make the API fail to boot.
    init_database()
    try:
        engine_service.start()
    except Exception as exc:
        print(f"[stockfish] warm-up failed, lazy retry will be used: {exc}")
    yield
    engine_service.stop()


app = FastAPI(title=settings.app_name, version="1.5.0", lifespan=lifespan)

origins = ["*"] if settings.frontend_origin == "*" else [settings.frontend_origin, "*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}
