import re
from decimal import Decimal

from app.extensions import db
from app.models import Customer, Product, Sale, SaleItem, StockMovement


def _csrf(client, path="/sales/nova"):
    response = client.get(path)
    assert response.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)


def _product(app, *, stock=5, price="12.50", cost="7.00", name="Colar"):
    with app.app_context():
        product = Product(
            code=f"JM-{name[:2].upper()}-000001",
            name=name,
            category="Acessórios",
            description="",
            cost_price=Decimal(cost),
            selling_price=Decimal(price),
            stock_quantity=stock,
            minimum_stock=1,
        )
        db.session.add(product)
        db.session.commit()
        return product.id


def _customer(app):
    with app.app_context():
        customer = Customer(
            name="Ana Marques",
            phone="(11) 98765-4321",
            normalized_phone="11987654321",
            email="",
            notes="",
        )
        db.session.add(customer)
        db.session.commit()
        return customer.id


def _token(response):
    return re.search(r'name="idempotency_key" value="([^"]+)"', response.get_data(as_text=True)).group(1)


def test_registro_de_venda_calcula_total_e_baixa_estoque_atomically(client, app):
    product_id = _product(app, stock=5, price="12.50")
    customer_id = _customer(app)
    page = client.get("/sales/nova")
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)

    response = client.post(
        "/sales/nova",
        data={
            "csrf_token": csrf_token,
            "idempotency_key": _token(page),
            "customer_id": str(customer_id),
            "payment_method": "pix",
            f"quantity_{product_id}": "2",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Venda registrada e estoque atualizado" in response.get_data(as_text=True)
    with app.app_context():
        sale = db.session.scalar(db.select(Sale))
        product = db.session.get(Product, product_id)
        item = db.session.scalar(db.select(SaleItem).where(SaleItem.sale_id == sale.id))
        movement = db.session.get(StockMovement, item.stock_movement_id)
        assert sale.total_amount == Decimal("25.00")
        assert sale.customer_name == "Ana Marques"
        assert item.unit_cost == Decimal("7.00")
        assert product.stock_quantity == 3
        assert movement.movement_type == "saida"
        assert movement.quantity == 2


def test_venda_recusa_estoque_insuficiente_sem_registro_parcial(client, app):
    product_id = _product(app, stock=1)
    page = client.get("/sales/nova")
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)

    response = client.post(
        "/sales/nova",
        data={
            "csrf_token": csrf_token,
            "idempotency_key": _token(page),
            "payment_method": "pix",
            f"quantity_{product_id}": "2",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Estoque insuficiente" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Sale)) == 0
        assert db.session.get(Product, product_id).stock_quantity == 1
        assert db.session.scalar(db.select(db.func.count()).select_from(StockMovement)) == 0


def test_envio_repetido_com_mesma_chave_nao_duplica_venda_ou_baixa(client, app):
    product_id = _product(app, stock=5)
    page = client.get("/sales/nova")
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    payload = {
        "csrf_token": csrf_token,
        "idempotency_key": _token(page),
        "payment_method": "dinheiro",
        f"quantity_{product_id}": "1",
    }

    first = client.post("/sales/nova", data=payload)
    second = client.post("/sales/nova", data=payload, follow_redirects=True)

    assert first.status_code == 302
    assert second.status_code == 200
    assert "já havia sido registrada" in second.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Sale)) == 1
        assert db.session.get(Product, product_id).stock_quantity == 4
        assert db.session.scalar(db.select(db.func.count()).select_from(StockMovement)) == 1


def test_venda_sem_produtos_ou_com_forma_de_pagamento_invalida_e_recusada(client, app):
    _product(app)
    page = client.get("/sales/nova")
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)

    response = client.post(
        "/sales/nova",
        data={
            "csrf_token": csrf_token,
            "idempotency_key": _token(page),
            "payment_method": "inventado",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "forma de pagamento válida" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Sale)) == 0


def test_venda_recusa_quantidade_nao_inteira_cliente_invalido_e_produto_inexistente(client, app):
    page = client.get("/sales/nova")
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    key = _token(page)

    for payload, expected_message in (
        ({"quantity_abc": "x"}, "Confira as quantidades"),
        ({"quantity_1": "1", "customer_id": "texto"}, "Selecione um cliente válido"),
        ({"quantity_999": "1"}, "produtos selecionados não está disponível"),
    ):
        response = client.post(
            "/sales/nova",
            data={"csrf_token": csrf_token, "idempotency_key": key, "payment_method": "pix", **payload},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert expected_message in response.get_data(as_text=True)


def test_detalhe_do_cliente_mostra_historico_de_vendas(client, app):
    product_id = _product(app, stock=2)
    customer_id = _customer(app)
    page = client.get("/sales/nova")
    csrf_token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)
    response = client.post(
        "/sales/nova",
        data={
            "csrf_token": csrf_token,
            "idempotency_key": _token(page),
            "customer_id": str(customer_id),
            "payment_method": "pix",
            f"quantity_{product_id}": "1",
        },
    )
    customer_response = client.get(f"/customers/{customer_id}")

    assert response.status_code == 302
    assert customer_response.status_code == 200
    assert "JM-V-" in customer_response.get_data(as_text=True)


def test_rotas_de_vendas_abrem_sem_login(anonymous_client):
    for path in ("/sales/", "/sales/nova"):
        assert anonymous_client.get(path).status_code == 200, path
