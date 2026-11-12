import re

from app.extensions import db
from app.models import Product, StockMovement


def csrf(client, path="/products/novo"):
    page = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', page).group(1)


def create_payload(token, **overrides):
    data = {
        "csrf_token": token,
        "name": "Café especial",
        "category": "Bebidas",
        "description": "Torra média",
        "cost_price": "18.50",
        "selling_price": "32.90",
        "stock_quantity": "8",
        "minimum_stock": "3",
    }
    data.update(overrides)
    return data


def add_product(app, **overrides):
    data = {
        "code": Product.next_code(), "name": "Café especial", "category": "Bebidas",
        "description": "", "cost_price": 10, "selling_price": 20,
        "stock_quantity": 5, "minimum_stock": 2,
    }
    data.update(overrides)
    product = Product(**data)
    db.session.add(product)
    db.session.commit()
    return product.id


def test_listagem_vazia_e_link_do_menu_funcional(client):
    response = client.get("/products/")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Seu catálogo começa aqui" in page
    assert 'href="/products/"' in page


def test_cadastro_gera_codigo_e_registra_saldo_inicial(client, app):
    response = client.post("/products/novo", data=create_payload(csrf(client)), follow_redirects=True)
    assert response.status_code == 200
    assert "Produto cadastrado com sucesso" in response.get_data(as_text=True)
    with app.app_context():
        product = db.session.scalar(db.select(Product))
        movement = db.session.scalar(db.select(StockMovement))
        assert product.code == "JM-000001"
        assert product.stock_quantity == 8
        assert movement.movement_type == "entrada"
        assert movement.quantity == 8


def test_busca_por_categoria_e_alerta_de_estoque_baixo(client, app):
    with app.app_context():
        add_product(app, stock_quantity=1, minimum_stock=2)
    response = client.get("/products/?q=Bebidas&baixo_estoque=1")
    page = response.get_data(as_text=True)
    assert response.status_code == 200
    assert "Café especial" in page
    assert "1 produto(s) no limite de estoque" in page


def test_edicao_atualiza_dados_sem_alterar_saldo(client, app):
    with app.app_context():
        product_id = add_product(app)
    token = csrf(client, f"/products/{product_id}/editar")
    response = client.post(f"/products/{product_id}/editar", data=create_payload(token, name="Café novo", stock_quantity="99"), follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        product = db.session.get(Product, product_id)
        assert product.name == "Café novo"
        assert product.stock_quantity == 5


def test_formulario_recusa_valores_negativos(client, app):
    response = client.post("/products/novo", data=create_payload(csrf(client), stock_quantity="-2"), follow_redirects=True)
    assert response.status_code == 200
    assert "não pode ser negativo" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Product)) == 0


def test_formulario_recusa_preco_com_mais_de_duas_casas(client, app):
    response = client.post("/products/novo", data=create_payload(csrf(client), cost_price="2.345"), follow_redirects=True)
    assert response.status_code == 200
    assert "até duas casas decimais" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Product)) == 0


def test_operacao_de_estoque_bloqueia_saida_acima_do_saldo(client, app):
    with app.app_context():
        product_id = add_product(app, stock_quantity=2)
    path = f"/products/{product_id}"
    token = csrf(client, path)
    response = client.post(f"/inventory/produtos/{product_id}/movimentacoes", data={"csrf_token": token, "movement_type": "saida", "quantity": "3", "reason": "Venda"}, follow_redirects=True)
    assert response.status_code == 200
    assert "maior que o estoque disponível" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Product, product_id).stock_quantity == 2
        assert db.session.scalar(db.select(db.func.count()).select_from(StockMovement)) == 0


def test_movimentacao_recusa_tipo_quantidade_ou_motivo_invalidos(client, app):
    with app.app_context():
        product_id = add_product(app)
    token = csrf(client, f"/products/{product_id}")
    endpoint = f"/inventory/produtos/{product_id}/movimentacoes"
    for data in [
        {"movement_type": "ajuste", "quantity": "1", "reason": "Ajuste"},
        {"movement_type": "entrada", "quantity": "0", "reason": "Reposição"},
        {"movement_type": "entrada", "quantity": "1", "reason": " "},
        {"movement_type": "entrada", "quantity": "abc", "reason": "Reposição"},
    ]:
        response = client.post(endpoint, data={**data, "csrf_token": token}, follow_redirects=True)
        assert response.status_code == 200
        assert "class=\"alert alert-danger" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Product, product_id).stock_quantity == 5
        assert db.session.scalar(db.select(db.func.count()).select_from(StockMovement)) == 0


def test_entrada_e_saida_registram_historico(client, app):
    with app.app_context():
        product_id = add_product(app, stock_quantity=2)
    token = csrf(client, f"/products/{product_id}")
    for kind, quantity, reason in [("entrada", "4", "Reposição"), ("saida", "3", "Ajuste")]:
        response = client.post(f"/inventory/produtos/{product_id}/movimentacoes", data={"csrf_token": token, "movement_type": kind, "quantity": quantity, "reason": reason})
        assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Product, product_id).stock_quantity == 3
        assert db.session.scalar(db.select(db.func.count()).select_from(StockMovement)) == 2


def test_remocao_exige_confirmacao_e_preserva_historico(client, app):
    with app.app_context():
        product_id = add_product(app, stock_quantity=1)
        db.session.add(StockMovement(product_id=product_id, movement_type="entrada", quantity=1, reason="Saldo inicial"))
        db.session.commit()
    assert client.get(f"/products/{product_id}/excluir").status_code == 200
    token = csrf(client, f"/products/{product_id}/excluir")
    response = client.post(f"/products/{product_id}/excluir", data={"csrf_token": token}, follow_redirects=True)
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Product, product_id).is_active is False
        assert db.session.scalar(db.select(db.func.count()).select_from(StockMovement)) == 1


def test_post_sem_csrf_e_recusado(client):
    assert client.post("/products/novo", data={}).status_code == 400
