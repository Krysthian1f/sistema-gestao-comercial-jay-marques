import re
from datetime import datetime, timezone
from decimal import Decimal

from app.extensions import db
from app.models import FinancialEntry, Product, Sale, SaleItem, StockMovement


def _create_product(app):
    with app.app_context():
        product = Product(
            code="JM-FIN-000001",
            name="Perfume",
            category="Cosméticos",
            description="",
            cost_price=Decimal("30.00"),
            selling_price=Decimal("50.00"),
            stock_quantity=4,
            minimum_stock=1,
        )
        db.session.add(product)
        db.session.commit()
        return product.id


def test_venda_cria_um_recebimento_vinculado_e_nao_duplica(client, app):
    product_id = _create_product(app)
    page = client.get("/sales/nova")
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    idempotency_key = re.search(r'name="idempotency_key" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    data = {
        "csrf_token": csrf_token,
        "idempotency_key": idempotency_key,
        "payment_method": "pix",
        f"quantity_{product_id}": "1",
    }

    first = client.post("/sales/nova", data=data)
    second = client.post("/sales/nova", data=data)

    assert first.status_code == second.status_code == 302
    with app.app_context():
        entry = db.session.scalar(db.select(FinancialEntry))
        assert entry.kind == "receita"
        assert entry.category == "Venda"
        assert entry.amount == Decimal("50.00")
        assert entry.sale_id is not None
        assert db.session.scalar(db.select(db.func.count()).select_from(FinancialEntry)) == 1


def test_lancamento_manual_valida_valor_e_persiste_receita_ou_despesa(client, app):
    response = client.get("/finance/novo")
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)
    key = re.search(r'name="idempotency_key" value="([^"]+)"', response.get_data(as_text=True)).group(1)

    response = client.post(
        "/finance/novo",
        data={
            "csrf_token": token,
            "idempotency_key": key,
            "kind": "despesa",
            "category": "Fornecedor",
            "description": "Compra de embalagens",
            "amount": "25,90",
            "occurred_on": "2026-11-16",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Lançamento financeiro registrado" in response.get_data(as_text=True)
    with app.app_context():
        entry = db.session.scalar(db.select(FinancialEntry))
        assert entry.kind == "despesa"
        assert entry.amount == Decimal("25.90")
        assert entry.sale_id is None


def test_financeiro_calcula_receita_saldo_e_lucro_estimado(client, app):
    product_id = _create_product(app)
    with app.app_context():
        product = db.session.get(Product, product_id)
        movement = StockMovement(product=product, movement_type="saida", quantity=2, reason="Venda de teste")
        db.session.add(movement)
        sale = Sale(
            code="JM-V-FINANCE",
            idempotency_key="f37ad601-cd4e-4e50-a7df-791fcaebef79",
            customer_name="Consumidor não identificado",
            payment_method="pix",
            total_amount=Decimal("100.00"),
            created_at=datetime(2026, 11, 16, 12, tzinfo=timezone.utc),
        )
        db.session.add(sale)
        db.session.flush()
        item = SaleItem(
            sale=sale,
            product=product,
            product_code=product.code,
            product_name=product.name,
            quantity=2,
            unit_price=Decimal("50.00"),
            unit_cost=Decimal("30.00"),
            subtotal=Decimal("100.00"),
            stock_movement=movement,
        )
        db.session.add(item)
        db.session.add(
            FinancialEntry(
                kind="receita",
                category="Venda",
                description="Recebimento teste",
                amount=Decimal("100.00"),
                occurred_at=sale.created_at,
                sale=sale,
            )
        )
        db.session.add(
            FinancialEntry(
                kind="despesa",
                category="Aluguel",
                description="Aluguel mensal",
                amount=Decimal("20.00"),
                occurred_at=sale.created_at,
            )
        )
        db.session.commit()

    response = client.get("/finance/", query_string={"inicio": "2026-11-16", "fim": "2026-11-16"})
    content = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "R$ 100,00" in content
    assert "R$ 20,00" in content
    assert "R$ 80,00" in content
    assert "R$ 20,00" in content


def test_formulario_financeiro_recusa_valores_invalidos(client, app):
    response = client.get("/finance/novo")
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)
    key = re.search(r'name="idempotency_key" value="([^"]+)"', response.get_data(as_text=True)).group(1)
    response = client.post(
        "/finance/novo",
        data={
            "csrf_token": token,
            "idempotency_key": key,
            "kind": "despesa",
            "category": "Fornecedor",
            "description": "Compra",
            "amount": "0",
            "occurred_on": "2026-11-16",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "maior que zero" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(FinancialEntry)) == 0


def test_reenvio_de_lancamento_manual_nao_cria_duplicidade(client, app):
    response = client.get("/finance/novo")
    token = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)
    key = re.search(r'name="idempotency_key" value="([^"]+)"', response.get_data(as_text=True)).group(1)
    payload = {
        "csrf_token": token,
        "idempotency_key": key,
        "kind": "receita",
        "category": "Outros",
        "description": "Receita extra",
        "amount": "10.00",
        "occurred_on": "2026-11-16",
    }

    first = client.post("/finance/novo", data=payload)
    second = client.post("/finance/novo", data=payload, follow_redirects=True)

    assert first.status_code == 302
    assert second.status_code == 200
    assert "já havia sido registrado" in second.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(FinancialEntry)) == 1


def test_filtro_financeiro_recusa_datas_invalidas_e_periodo_invertido(client):
    invalid = client.get("/finance/?inicio=ontem")
    reversed_range = client.get("/finance/?inicio=2026-11-17&fim=2026-11-16")

    assert invalid.status_code == reversed_range.status_code == 200
    assert "Informe uma data válida" in invalid.get_data(as_text=True)
    assert "data inicial deve ser anterior" in reversed_range.get_data(as_text=True)


def test_rotas_financeiras_exigem_login(anonymous_client):
    for path in ("/finance/", "/finance/novo"):
        response = anonymous_client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"].split("?", 1)[0].endswith("/login")
