from __future__ import annotations

import secrets
import os
from pathlib import Path

from flask import Flask

from app.extensions import db, login_manager


def _load_or_create_secret_key(instance_path: Path) -> str:
    """Load a stable local key, creating one if the operator did not provide it."""
    configured_key = os.environ.get("SECRET_KEY")
    if configured_key:
        return configured_key

    key_path = instance_path / ".secret_key"
    try:
        return key_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        key = secrets.token_urlsafe(48)
        try:
            key_path.write_text(key, encoding="utf-8")
        except FileExistsError:
            return key_path.read_text(encoding="utf-8").strip()
        return key


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config.from_object("config.Config")
    app.config["SECRET_KEY"] = app.config.get("SECRET_KEY") or _load_or_create_secret_key(
        Path(app.instance_path)
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(_user_id: str):
        # Fase 2: replace this placeholder with a lookup in the user model.
        return None

    from app.dashboard import dashboard

    app.register_blueprint(dashboard)

    with app.app_context():
        # Open once so SQLite creates its local file even before feature tables exist.
        db.engine.connect().close()
        db.create_all()

    return app
