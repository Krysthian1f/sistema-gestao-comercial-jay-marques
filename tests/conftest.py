from pathlib import Path

import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app(tmp_path: Path):
    database_path = tmp_path / "test.sqlite"
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "chave-segura-de-teste",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        }
    )

    yield application

    with application.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()
