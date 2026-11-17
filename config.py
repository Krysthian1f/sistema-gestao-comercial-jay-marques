import os
from pathlib import Path
from datetime import timedelta


BASE_DIR = Path(__file__).resolve().parent


def _as_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _database_uri() -> str:
    configured_uri = os.environ.get("DATABASE_URL")
    if configured_uri:
        return normalize_database_uri(configured_uri)

    sqlite_data_dir = os.environ.get("SQLITE_DATA_DIR")
    if sqlite_data_dir:
        database_path = Path(sqlite_data_dir) / "gestao_comercial.sqlite"
    else:
        database_path = BASE_DIR / "instance" / "gestao_comercial.sqlite"
    return f"sqlite:///{database_path.as_posix()}"


def normalize_database_uri(uri: str) -> str:
    """Select psycopg 3 explicitly while preserving Neon URL options."""
    if uri.startswith("postgres://"):
        return "postgresql+psycopg://" + uri.removeprefix("postgres://")
    if uri.startswith("postgresql://"):
        return "postgresql+psycopg://" + uri.removeprefix("postgresql://")
    return uri


def _secure_cookies() -> bool:
    return _is_production() or _as_bool(os.environ.get("SESSION_COOKIE_SECURE"))


def _is_production() -> bool:
    return (
        _as_bool(os.environ.get("RENDER"))
        or bool(os.environ.get("KOYEB_APP_NAME") or os.environ.get("KOYEB_SERVICE_NAME"))
        or os.environ.get("APP_ENV", "").lower() == "production"
    )


class Config:
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"
    IS_PRODUCTION = _is_production()
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _database_uri()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Enforce HTTPS-only cookies in production, while keeping local HTTP usable.
    SESSION_COOKIE_SECURE = _secure_cookies()
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_REFRESH_EACH_REQUEST = True
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15
