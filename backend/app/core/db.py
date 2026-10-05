from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None
DATABASE_AVAILABLE = False
DATABASE_ERROR: str | None = None
DATABASE_KIND = "disabled"


def _build_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    kwargs = {
        "pool_pre_ping": True,
        "connect_args": connect_args,
    }
    if not url.startswith("sqlite"):
        kwargs["pool_recycle"] = 300
    return create_engine(url, **kwargs)


def init_database() -> bool:
    """Initialise persistent storage if configured.

    The chess application must stay usable even when PostgreSQL is missing,
    expired or temporarily unavailable. All core chess features therefore run
    without a database; only persistence is disabled in that case.
    """
    global engine, SessionLocal, DATABASE_AVAILABLE, DATABASE_ERROR, DATABASE_KIND

    url = (settings.database_url or "").strip()
    if not url:
        engine = None
        SessionLocal = None
        DATABASE_AVAILABLE = False
        DATABASE_ERROR = None
        DATABASE_KIND = "disabled"
        return False

    try:
        candidate = _build_engine(url)
        with candidate.connect() as conn:
            conn.execute(text("SELECT 1"))
        Base.metadata.create_all(bind=candidate)
        engine = candidate
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        DATABASE_AVAILABLE = True
        DATABASE_ERROR = None
        DATABASE_KIND = "sqlite" if url.startswith("sqlite") else "postgresql"
        return True
    except Exception as exc:
        engine = None
        SessionLocal = None
        DATABASE_AVAILABLE = False
        DATABASE_ERROR = f"{type(exc).__name__}: {exc}"
        DATABASE_KIND = "unavailable"
        print(f"[database] persistence disabled: {DATABASE_ERROR}")
        return False


def database_status() -> dict:
    return {
        "available": DATABASE_AVAILABLE,
        "kind": DATABASE_KIND,
        "error": DATABASE_ERROR,
    }


def get_db() -> Generator[Session | None, None, None]:
    """Yield a DB session when persistence is available, otherwise None."""
    if not DATABASE_AVAILABLE or SessionLocal is None:
        yield None
        return

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
