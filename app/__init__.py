from __future__ import annotations

import os
import hmac
import secrets
from pathlib import Path

import click
from flask import Flask, abort, request, session
from flask_login import current_user
from werkzeug.security import generate_password_hash

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
            with key_path.open("x", encoding="utf-8") as key_file:
                key_file.write(key)
        except FileExistsError:
            return key_path.read_text(encoding="utf-8").strip()
        return key


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    app.config.from_object("config.Config")
    if test_config is not None:
        app.config.update(test_config)
    app.config["SECRET_KEY"] = app.config.get("SECRET_KEY") or _load_or_create_secret_key(
        Path(app.instance_path)
    )

    db.init_app(app)
    login_manager.init_app(app)

    @app.context_processor
    def inject_csrf_token():
        def csrf_token():
            if "csrf_token" not in session:
                session["csrf_token"] = secrets.token_urlsafe(32)
            return session["csrf_token"]

        return {"csrf_token": csrf_token}

    @app.before_request
    def protect_application():
        if request.endpoint == "static":
            return None
        owner_authenticated = (
            current_user.is_authenticated
            and current_user.is_active
            and current_user.is_admin
        )
        if request.endpoint != "auth.login" and not owner_authenticated:
            return login_manager.unauthorized()
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            supplied = request.form.get("csrf_token", "")
            expected = session.get("csrf_token", "")
            if not expected or not hmac.compare_digest(supplied, expected):
                abort(400, description="Token de segurança inválido. Atualize a página e tente novamente.")
        return None

    @login_manager.user_loader
    def load_user(user_id: str):
        from app.models import User

        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from app.models import Product, StockMovement, User  # noqa: F401
    from app.auth import auth
    from app.dashboard import dashboard
    from app.products import products
    from app.inventory import inventory

    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(products)
    app.register_blueprint(inventory)

    with app.app_context():
        # Open once so SQLite creates its local file even before feature tables exist.
        db.engine.connect().close()
        db.create_all()

    @app.cli.command("create-admin")
    def create_admin_command():
        """Cria a única conta administrativa solicitando a senha sem exibi-la."""
        if db.session.scalar(db.select(db.func.count()).select_from(User)):
            raise click.ClickException("Já existe uma conta cadastrada. O comando não altera nem redefine credenciais.")

        password = click.prompt(
            "Senha inicial para o usuário vida (mínimo 12 caracteres)",
            hide_input=True,
            confirmation_prompt=True,
        )
        if len(password) < 12:
            raise click.ClickException("A senha precisa ter pelo menos 12 caracteres. Nenhuma conta foi criada.")

        admin = User(username="vida", password_hash=generate_password_hash(password), is_admin=True)
        db.session.add(admin)
        db.session.commit()
        click.echo("Conta administrativa vida criada com hash de senha. Guarde a senha em local seguro.")

    return app
