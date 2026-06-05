from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.config import Config


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_database_url(hide_password: bool = True) -> str:
    url = make_url(Config.DATABASE_URL)
    return url.render_as_string(hide_password=hide_password)


def get_engine() -> Engine:
    global _engine

    if _engine is None:
        _engine = create_engine(
            Config.DATABASE_URL,
            pool_pre_ping=True,
            pool_recycle=3600,
        )

    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory

    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)

    return _session_factory


def create_session() -> Session:
    return get_session_factory()()


def check_database_connection() -> dict:
    try:
        with get_engine().connect() as connection:
            version = connection.execute(text("SELECT VERSION()")).scalar_one()

        return {
            "ok": True,
            "status": "connected",
            "version": version,
            "database_url": get_database_url(),
        }
    except SQLAlchemyError as exc:
        root_error = exc.__cause__ or exc
        return {
            "ok": False,
            "status": "error",
            "message": "Database connection failed.",
            "error": str(root_error),
            "database_url": get_database_url(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "error",
            "message": "Unexpected database health check error.",
            "error": str(exc),
            "database_url": get_database_url(),
        }
