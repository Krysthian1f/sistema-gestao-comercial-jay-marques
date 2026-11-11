import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


class Config:
    DEBUG = os.environ.get("FLASK_DEBUG") == "1"
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'instance' / 'gestao_comercial.sqlite').as_posix()}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
