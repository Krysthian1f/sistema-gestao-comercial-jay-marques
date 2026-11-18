from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.extensions import db
from app.models import StockMovement


def test_fabrica_sem_test_config_usa_sqlite_temporario(monkeypatch, tmp_path: Path):
    from config import Config

    database_path = tmp_path / "factory.sqlite"
    monkeypatch.setattr(
        Config, "SQLALCHEMY_DATABASE_URI", f"sqlite:///{database_path.as_posix()}"
    )
    monkeypatch.setattr(Config, "SECRET_KEY", "chave-do-modo-padrao")

    application = create_app()

    try:
        assert application.testing is False
        assert application.config["SECRET_KEY"] == "chave-do-modo-padrao"

        with application.test_client() as client:
            response = client.get("/")

        assert response.status_code == 200
        with application.app_context():
            assert Path(db.engine.url.database).resolve() == database_path.resolve()
            assert database_path.is_file()
    finally:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()


def test_sessao_antiga_nao_impede_acesso(client):
    with client.session_transaction() as session:
        session["_user_id"] = "usuario-inexistente"
        session["_fresh"] = True

    response = client.get("/")

    assert response.status_code == 200


def test_arquivo_css_estatico_e_servido(client):
    response = client.get("/static/css/style.css")

    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert ":root" in response.get_data(as_text=True)


def test_dashboard_recusa_metodo_post(client):
    with client.session_transaction() as session:
        session["csrf_token"] = "token-de-teste"
    response = client.post("/", data={"csrf_token": "token-de-teste"})

    assert response.status_code == 405


def test_rota_inexistente_responde_404(client):
    response = client.get("/rota-que-nao-existe")

    assert response.status_code == 404


def test_sqlite_habilita_chaves_estrangeiras_e_recusa_referencias_invalidas(app):
    with app.app_context():
        assert db.session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        db.session.add(StockMovement(
            product_id=999999,
            movement_type="entrada",
            quantity=1,
            reason="Referência inexistente",
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()


def test_relatorio_exibe_vendas_e_exporta_csv(client, app):
    from decimal import Decimal

    from app.models import Sale

    with app.app_context():
        db.session.add(Sale(
            code="JM-V-CSV00001",
            idempotency_key="676a6f40-a4ef-49eb-9a18-28ba47342452",
            customer_name="Ana",
            payment_method="pix",
            total_amount=Decimal("49.90"),
        ))
        db.session.commit()

    page = client.get("/reports/?tipo=vendas")
    report = client.get("/reports/exportar.csv?tipo=vendas")

    assert page.status_code == 200
    assert "JM-V-CSV00001" in page.get_data(as_text=True)
    assert report.status_code == 200
    assert report.mimetype == "text/csv"
    assert "Código,Data,Cliente" in report.get_data(as_text=True)
    assert "JM-V-CSV00001" in report.get_data(as_text=True)


def test_relatorio_csv_escapa_formula_de_planilha(client, app):
    from app.models import Product
    from decimal import Decimal

    with app.app_context():
        db.session.add(Product(
            code="JM-CSV-000001", name="=HYPERLINK(\"x\")", category="Acessórios",
            description="", cost_price=Decimal("1"), selling_price=Decimal("2"),
            stock_quantity=1, minimum_stock=0,
        ))
        db.session.commit()

    response = client.get("/reports/exportar.csv?tipo=produtos")
    content = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "'=HYPERLINK" in content
