import re
from pathlib import Path

from sqlalchemy import inspect

from app.extensions import db


def test_app_inicia_em_modo_de_testes_com_sqlite_temporario(app, tmp_path: Path):
    assert app.testing is True
    assert app.config["SECRET_KEY"] == "chave-segura-de-teste"

    with app.app_context():
        database_path = Path(db.engine.url.database).resolve()
        tables = inspect(db.engine).get_table_names()

    assert database_path.parent == tmp_path.resolve()
    assert database_path.name == "test.sqlite"
    assert database_path.is_file()
    assert tables == ["customers", "financial_entries", "products", "sale_items", "sales", "stock_movements", "users"]


def test_rota_principal_responde_com_pagina_do_dashboard(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "Visão geral | Jay Marques" in response.get_data(as_text=True)


def test_dashboard_renderiza_conteudo_e_data_em_portugues(client):
    response = client.get("/")
    page = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Bem-vindo, Jay" in page
    assert "Resumo do sistema" in page
    assert re.search(r"\b\d{2}/\d{2}/\d{4}\b", page)


def test_dashboard_sem_registros_exibe_estados_vazios(client, app):
    response = client.get("/")
    page = response.get_data(as_text=True)

    with app.app_context():
        assert inspect(db.engine).get_table_names() == [
            "customers", "financial_entries", "products", "sale_items", "sales", "stock_movements", "users"
        ]

    assert "atualizado com os dados cadastrados" in page
    assert "Nenhuma atividade por enquanto" in page
    assert '<div class="metric-value">0</div>' in page
    assert "Clientes ativos cadastrados" in page
    assert "Vendas registradas" in page


def test_health_publico_confirma_conexao_com_banco(anonymous_client):
    response = anonymous_client.get("/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok", "database": "available"}


def test_dashboard_mostra_contagens_reais_dos_modulos(client, app):
    from decimal import Decimal

    from app.models import Customer, FinancialEntry, Product, Sale

    with app.app_context():
        db.session.add(Product(
            code="JM-DASH-001", name="Bolsa", category="Roupas", description="",
            cost_price=Decimal("20"), selling_price=Decimal("35"), stock_quantity=2, minimum_stock=1,
        ))
        db.session.add(Customer(name="Bia", phone="11999990000", normalized_phone="11999990000"))
        sale = Sale(
            code="JM-V-DASH001", idempotency_key="cb2b609b-6a0b-4f2a-995a-302fc9bf2abc",
            customer_name="Bia", payment_method="pix", total_amount=Decimal("35"),
        )
        db.session.add(sale)
        db.session.flush()
        db.session.add(FinancialEntry(
            kind="receita", category="Venda", description="Recebimento venda",
            amount=Decimal("35"), occurred_at=sale.created_at, sale=sale,
        ))
        db.session.commit()

    response = client.get("/")
    content = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Clientes ativos cadastrados" in content
    assert "Vendas registradas" in content
    assert "R$ 35,00" in content


def test_configuracao_de_teste_com_chave_propria_nao_carrega_chave_local(monkeypatch):
    import app as app_module

    def fail_if_local_secret_is_loaded(_instance_path):
        raise AssertionError("A chave local não deve ser carregada nesta configuração de teste.")

    monkeypatch.setattr(app_module, "_load_or_create_secret_key", fail_if_local_secret_is_loaded)
    application = app_module.create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "chave-segura-de-teste",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )

    assert application.config["SECRET_KEY"] == "chave-segura-de-teste"

    with application.app_context():
        db.session.remove()
        db.engine.dispose()
