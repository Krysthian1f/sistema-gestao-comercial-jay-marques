from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models import FinancialEntry, Product, StockMovement


def test_relatorios_de_produto_estoque_e_financeiro_mostram_dados_real(client, app):
    with app.app_context():
        product = Product(
            code="JM-RPT-000001", name="Brinco", category="Joias", description="",
            cost_price=Decimal("8.00"), selling_price=Decimal("19.90"), stock_quantity=3, minimum_stock=1,
            created_at=datetime(2026, 11, 16, 10, tzinfo=timezone.utc),
        )
        db.session.add(product)
        db.session.flush()
        db.session.add(StockMovement(
            product=product, movement_type="entrada", quantity=3, reason="Reposição do fornecedor",
            created_at=datetime(2026, 11, 16, 12, tzinfo=timezone.utc),
        ))
        db.session.add(FinancialEntry(
            kind="despesa", category="Fornecedor", description="Compra de brincos",
            amount=Decimal("24.00"), occurred_at=datetime(2026, 11, 16, 12, tzinfo=timezone.utc),
        ))
        db.session.commit()

    product_report = client.get("/reports/?tipo=produtos&inicio=2026-11-16&fim=2026-11-16")
    stock_report = client.get("/reports/?tipo=estoque&inicio=2026-11-16&fim=2026-11-16")
    finance_csv = client.get("/reports/exportar.csv?tipo=financeiro&inicio=2026-11-16&fim=2026-11-16")

    assert "JM-RPT-000001" in product_report.get_data(as_text=True)
    assert "Brinco" in stock_report.get_data(as_text=True)
    assert "Compra de brincos" in finance_csv.get_data(as_text=True)
    assert finance_csv.mimetype == "text/csv"


def test_relatorios_rejeitam_intervalo_invertido_e_tipo_csv_invalido(client):
    invalid_page = client.get("/reports/?tipo=vendas&inicio=2026-11-17&fim=2026-11-16")
    invalid_csv = client.get("/reports/exportar.csv?tipo=secreto")
    invalid_date_csv = client.get("/reports/exportar.csv?tipo=vendas&inicio=ontem")

    assert invalid_page.status_code == 200
    assert "data inicial deve ser anterior" in invalid_page.get_data(as_text=True)
    assert invalid_csv.status_code == 400
    assert invalid_date_csv.status_code == 400
