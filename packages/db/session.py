from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from packages.config import Settings
from packages.db import models  # noqa: F401
from packages.db.schema import Base


def create_session_factory(settings: Settings) -> sessionmaker | None:
    if not settings.enable_db_persistence:
        return None
    db_url = settings.database_url
    if db_url.startswith("postgresql") or db_url.startswith("sqlite"):
        connect_url = db_url
    else:
        sqlite_path = Path(settings.sqlite_fallback_path)
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        connect_url = f"sqlite:///{sqlite_path.as_posix()}"
    engine = create_engine(connect_url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
