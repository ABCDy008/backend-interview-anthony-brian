from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Provide the SQLAlchemy declarative base for application models."""


def _connect_args(database_url: str) -> dict:
    """Build PostgreSQL connection arguments from the configured database URL."""
    return {"check_same_thread": False} if database_url.startswith("sqlite") else {}


engine = create_engine(
    get_settings().database_url,
    connect_args=_connect_args(get_settings().database_url),
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session]:
    """Yield a database session and close it after request processing."""
    with SessionLocal() as session:
        yield session
