from __future__ import annotations

import os
import hmac
import secrets
from pathlib import Path

import click
from flask import Flask, abort, request, session
from flask_login import current_user
from sqlalchemy import event, text
from werkzeug.security import generate_password_hash

from app.extensions import db, login_manager
from app.timeutils import format_brasilia_date, format_brasilia_datetime


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
    app.add_template_filter(format_brasilia_date, "data_br")
    app.add_template_filter(format_brasilia_datetime, "data_hora_br")
    if test_config is not None:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        if app.config.get("IS_PRODUCTION"):
            raise RuntimeError("Configure SECRET_KEY como variável de ambiente antes de iniciar em produção.")
        app.config["SECRET_KEY"] = _load_or_create_secret_key(Path(app.instance_path))

    if app.config.get("IS_PRODUCTION") and app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:"):
        if not os.environ.get("SQLITE_DATA_DIR"):
            raise RuntimeError(
                "Em produção, configure DATABASE_URL para PostgreSQL ou SQLITE_DATA_DIR em um disco persistente."
            )
        Path(os.environ["SQLITE_DATA_DIR"]).mkdir(parents=True, exist_ok=True)

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
        if request.endpoint not in {"auth.login", "health"} and not owner_authenticated:
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

    from app.models import Customer, FinancialEntry, Product, Sale, SaleItem, StockMovement, User  # noqa: F401
    from app.auth import auth
    from app.dashboard import dashboard
    from app.products import products
    from app.inventory import inventory
    from app.customers import customers
    from app.sales import sales
    from app.finance import finance
    from app.reports import reports

    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(products)
    app.register_blueprint(inventory)
    app.register_blueprint(customers)
    app.register_blueprint(sales)
    app.register_blueprint(finance)
    app.register_blueprint(reports)

    @app.get("/health")
    def health():
        from flask import jsonify

        try:
            db.session.execute(text("SELECT 1"))
            db.session.rollback()
        except Exception:
            db.session.rollback()
            return jsonify(status="unavailable", database="unavailable"), 503
        return jsonify(status="ok", database="available"), 200

    with app.app_context():
        if db.engine.dialect.name == "sqlite":
            @event.listens_for(db.engine, "connect")
            def enable_sqlite_foreign_keys(connection, _connection_record):
                cursor = connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        # Validate the configured database connection before serving requests.
        db.engine.connect().close()
        # Local development and tests may create their isolated schema automatically.
        # Production schema creation is explicit through init_neon_db.py after validation.
        if not app.config.get("IS_PRODUCTION") or app.config.get("AUTO_CREATE_DB", False):
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
