import re
import secrets

import click
from flask_login import current_user
from sqlalchemy import inspect
from werkzeug.security import check_password_hash

from app.extensions import db
from app.models import Product, User


def csrf_token(client):
    page = client.get("/login").get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)


def login(client, password, username="vida"):
    return client.post(
        "/login",
        data={"csrf_token": csrf_token(client), "username": username, "password": password},
    )


def test_login_com_credenciais_validas_autentica_somente_administradora(anonymous_client, app, owner, owner_password):
    response = login(anonymous_client, owner_password)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with anonymous_client:
        anonymous_client.get("/")
        assert current_user.is_authenticated
        assert current_user.username == "vida"
        assert current_user.is_admin is True
    with app.app_context():
        user = db.session.get(User, owner)
        assert user.failed_login_attempts == 0
        assert user.last_login_at is not None


def test_login_incorreto_nao_autentica_e_incrementa_tentativa(anonymous_client, app, owner, owner_password):
    response = login(anonymous_client, password=secrets.token_urlsafe(18))
    assert response.status_code == 200
    assert "Usuário ou senha incorretos" in response.get_data(as_text=True)
    with app.app_context():
        user = db.session.get(User, owner)
        assert user.failed_login_attempts == 1
        assert user.password_hash != owner_password
        assert check_password_hash(user.password_hash, owner_password)


def test_login_bloqueia_temporariamente_apos_tentativas_excessivas(anonymous_client, app, owner, owner_password):
    token = csrf_token(anonymous_client)
    wrong_password = secrets.token_urlsafe(18)
    for _ in range(app.config["MAX_LOGIN_ATTEMPTS"]):
        response = anonymous_client.post(
            "/login",
            data={"csrf_token": token, "username": "vida", "password": wrong_password},
        )
    assert "temporariamente bloqueado" in response.get_data(as_text=True)
    with app.app_context():
        user = db.session.get(User, owner)
        assert user.failed_login_attempts == app.config["MAX_LOGIN_ATTEMPTS"]
        assert user.locked_until is not None

    denied = anonymous_client.post(
        "/login",
        data={"csrf_token": token, "username": "vida", "password": owner_password},
    )
    assert "bloqueio temporário" in denied.get_data(as_text=True)


def test_login_sem_token_csrf_e_recusado(anonymous_client):
    assert anonymous_client.post("/login", data={"username": "vida"}).status_code == 400


def test_rotas_internas_exigem_autenticacao(anonymous_client):
    paths = ["/", "/products/", "/products/novo", "/products/999999", "/products/999999/editar", "/products/999999/excluir"]
    for path in paths:
        response = anonymous_client.get(path)
        assert response.status_code == 302, path
        assert response.headers["Location"].split("?", 1)[0].endswith("/login"), path
    response = anonymous_client.post("/inventory/produtos/999999/movimentacoes")
    assert response.status_code == 302
    assert response.headers["Location"].split("?", 1)[0].endswith("/login")


def test_logout_invalida_sessao_e_protege_operacoes_futuras(client):
    with client.session_transaction() as session:
        token = session["csrf_token"]
    response = client.post("/sair", data={"csrf_token": token})
    assert response.status_code == 302
    assert response.headers["Location"].split("?", 1)[0].endswith("/login")
    assert client.get("/").headers["Location"].split("?", 1)[0].endswith("/login")


def test_acesso_negado_preserva_produtos_existentes(anonymous_client, app, owner):
    with app.app_context():
        product = Product(
            code="JM-000001", name="Registro preservado", category="Teste",
            cost_price=1, selling_price=2, stock_quantity=4, minimum_stock=1,
        )
        db.session.add(product)
        db.session.commit()
        product_id = product.id

    assert anonymous_client.get("/products/").status_code == 302
    with app.app_context():
        assert db.session.get(Product, product_id).name == "Registro preservado"
        assert db.session.scalar(db.select(db.func.count()).select_from(User)) == 1


def test_cookie_de_sessao_tem_http_only_e_same_site(app, anonymous_client):
    response = anonymous_client.get("/login")
    cookie = next(value for key, value in response.headers if key.lower() == "set-cookie" and "session=" in value)
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert app.config["PERMANENT_SESSION_LIFETIME"].total_seconds() == 1800


def test_tela_de_login_mantem_marca_temas_e_acessibilidade(anonymous_client):
    page = anonymous_client.get("/login").get_data(as_text=True)
    stylesheet = anonymous_client.get("/static/css/style.css").get_data(as_text=True)
    assert 'alt="Marques Stores"' in page
    assert 'data-theme-toggle' in page
    assert 'data-font-increase' in page and 'data-font-decrease' in page and 'data-font-reset' in page
    assert 'data-password-toggle' in page
    assert "Desenvolvido por Krysthian" in page
    assert "@media (max-width: 430px)" in stylesheet
    assert ".login-card" in stylesheet


def test_comando_cria_uma_conta_com_hash_sem_exibir_senha(app, monkeypatch):
    admin_password = secrets.token_urlsafe(24)
    monkeypatch.setattr(click, "prompt", lambda *_args, **_kwargs: admin_password)
    result = app.test_cli_runner().invoke(args=["create-admin"])
    assert result.exit_code == 0, result.output
    assert admin_password not in result.output
    with app.app_context():
        users = db.session.scalars(db.select(User)).all()
        assert len(users) == 1
        assert users[0].username == "vida"
        assert users[0].is_admin is True
        assert check_password_hash(users[0].password_hash, admin_password)
        assert users[0].password_hash != admin_password


def test_comando_nao_cria_outra_conta_se_a_senha_for_curta(app, monkeypatch):
    monkeypatch.setattr(click, "prompt", lambda *_args, **_kwargs: "x" * 11)
    result = app.test_cli_runner().invoke(args=["create-admin"])
    assert result.exit_code != 0
    assert "pelo menos 12 caracteres" in result.output
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(User)) == 0
        assert set(inspect(db.engine).get_table_names()) == {"products", "stock_movements", "users"}
