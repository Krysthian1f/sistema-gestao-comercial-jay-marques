from pathlib import Path
import re
import secrets

import pytest

from app import create_app
from app.extensions import db
from app.models import User
from werkzeug.security import generate_password_hash


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
def owner_password():
    return secrets.token_urlsafe(24)


@pytest.fixture
def owner(app, owner_password):
    with app.app_context():
        user = User(
            username="vida",
            password_hash=generate_password_hash(owner_password),
            is_admin=True,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
    return user_id


@pytest.fixture
def anonymous_client(app):
    return app.test_client()


@pytest.fixture
def client(app, owner, owner_password):
    test_client = app.test_client()
    login_page = test_client.get("/login").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', login_page).group(1)
    with app.app_context():
        user = db.session.get(User, owner)
        username = user.username
    response = test_client.post(
        "/login",
        data={"csrf_token": token, "username": username, "password": owner_password},
    )
    assert response.status_code == 302
    test_client.get("/")
    return test_client
