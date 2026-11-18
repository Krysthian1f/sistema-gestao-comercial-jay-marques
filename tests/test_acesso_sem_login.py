from decimal import Decimal

from app.extensions import db
from app.models import Product, User


def _csrf_token(client):
    with client.session_transaction() as session:
        return session["csrf_token"]


def test_pagina_de_login_e_logout_foram_removidos(client):
    assert client.get("/login").status_code == 404
    assert client.get("/sair").status_code == 404

    with client.session_transaction() as session:
        session["csrf_token"] = "token-de-teste"

    assert client.post("/sair", data={"csrf_token": "token-de-teste"}).status_code == 404


def test_painel_abre_sem_login(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Visão geral" in response.get_data(as_text=True)


def test_todos_os_modulos_abrem_sem_login(client):
    paths = [
        "/",
        "/products/",
        "/products/novo",
        "/customers/",
        "/customers/novo",
        "/sales/",
        "/sales/nova",
        "/finance/",
        "/finance/novo",
        "/reports/",
    ]
    for path in paths:
        assert client.get(path).status_code == 200, path


def test_formulario_cria_produto_sem_login(client, app):
    client.get("/products/novo")
    token = _csrf_token(client)
    response = client.post(
        "/products/novo",
        data={
            "csrf_token": token,
            "name": "Produto sem login",
            "category": "Teste",
            "description": "",
            "cost_price": "10,00",
            "selling_price": "20,00",
            "stock_quantity": "3",
            "minimum_stock": "1",
        },
    )

    assert response.status_code == 302
    with app.app_context():
        product = db.session.scalar(
            db.select(Product).where(Product.name == "Produto sem login")
        )
        assert product is not None
        assert product.stock_quantity == 3


def test_escrita_sem_token_csrf_continua_recusada(client):
    response = client.post(
        "/products/novo",
        data={
            "name": "Sem token",
            "category": "Teste",
            "description": "",
            "cost_price": "1",
            "selling_price": "2",
            "stock_quantity": "1",
            "minimum_stock": "0",
        },
    )

    assert response.status_code == 400


def test_sessao_antiga_nao_bloqueia_nem_redireciona(client):
    with client.session_transaction() as session:
        session["_user_id"] = "usuario-inexistente"
        session["_fresh"] = True

    response = client.get("/products/")

    assert response.status_code == 200


def test_acesso_livre_preserva_registros_existentes(client, app):
    with app.app_context():
        db.session.add(Product(
            code="JM-000001",
            name="Registro preservado",
            category="Teste",
            description="",
            cost_price=Decimal("1"),
            selling_price=Decimal("2"),
            stock_quantity=4,
            minimum_stock=1,
        ))
        db.session.commit()

    for path in ("/", "/products/", "/customers/", "/sales/", "/finance/", "/reports/"):
        assert client.get(path).status_code == 200, path

    with app.app_context():
        assert db.session.scalar(db.select(Product).where(Product.code == "JM-000001")) is not None
        assert db.session.scalar(db.select(db.func.count()).select_from(User)) == 0


def test_comando_create_admin_foi_removido(app):
    assert "create-admin" not in app.cli.commands
