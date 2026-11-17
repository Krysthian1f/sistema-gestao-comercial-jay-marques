import re

from app.extensions import db
from app.models import Customer


def _csrf(client, path="/customers/novo"):
    response = client.get(path)
    assert response.status_code == 200
    return re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True)).group(1)


def _payload(token, **overrides):
    data = {
        "csrf_token": token,
        "name": "Ana Marques",
        "phone": "(11) 98765-4321",
        "email": "ana@example.com",
        "notes": "Cliente da loja.",
    }
    data.update(overrides)
    return data


def _create_customer(app, **overrides):
    values = {
        "name": "Ana Marques",
        "phone": "(11) 98765-4321",
        "normalized_phone": "11987654321",
        "email": "ana@example.com",
        "notes": "Cliente da loja.",
    }
    values.update(overrides)
    with app.app_context():
        customer = Customer(**values)
        db.session.add(customer)
        db.session.commit()
        return customer.id


def test_lista_de_clientes_vazia_e_link_do_menu_funcional(client):
    response = client.get("/customers/")

    assert response.status_code == 200
    assert "Sua lista de clientes começa aqui" in response.get_data(as_text=True)
    assert 'href="/customers/"' in response.get_data(as_text=True)


def test_cadastro_persiste_cliente_e_normaliza_telefone(client, app):
    token = _csrf(client)
    response = client.post("/customers/novo", data=_payload(token), follow_redirects=True)

    assert response.status_code == 200
    assert "Cliente cadastrado com sucesso" in response.get_data(as_text=True)
    with app.app_context():
        customer = db.session.scalar(db.select(Customer))
        assert customer.name == "Ana Marques"
        assert customer.normalized_phone == "11987654321"


def test_edicao_atualiza_cliente_sem_criar_outro(client, app):
    customer_id = _create_customer(app)
    token = _csrf(client, f"/customers/{customer_id}/editar")

    response = client.post(
        f"/customers/{customer_id}/editar",
        data=_payload(token, name="Ana Silva", phone="(21) 91234-5678"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Customer)) == 1
        customer = db.session.get(Customer, customer_id)
        assert customer.name == "Ana Silva"
        assert customer.normalized_phone == "21912345678"


def test_busca_localiza_nome_telefone_e_email(client, app):
    _create_customer(app)

    for query in ("Ana", "98765", "ana@example.com"):
        response = client.get("/customers/", query_string={"q": query})
        assert response.status_code == 200
        assert "Ana Marques" in response.get_data(as_text=True)


def test_nao_permite_telefone_duplicado_com_formatacao_diferente(client, app):
    _create_customer(app)
    token = _csrf(client)

    response = client.post(
        "/customers/novo",
        data=_payload(token, phone="11 98765-4321"),
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Já existe um cliente cadastrado com esse telefone" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Customer)) == 1


def test_validacao_recusa_telefone_e_email_invalidos(client, app):
    token = _csrf(client)
    response = client.post("/customers/novo", data=_payload(token, phone="123", email="invalido"))

    assert response.status_code == 200
    assert "telefone brasileiro com DDD" in response.get_data(as_text=True)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count()).select_from(Customer)) == 0


def test_exclusao_logica_preserva_registro_e_tira_da_listagem(client, app):
    customer_id = _create_customer(app)
    page = client.get(f"/customers/{customer_id}/excluir")
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.get_data(as_text=True)).group(1)

    response = client.post(
        f"/customers/{customer_id}/excluir",
        data={"csrf_token": token},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Ana Marques" not in response.get_data(as_text=True)
    with app.app_context():
        customer = db.session.get(Customer, customer_id)
        assert customer is not None
        assert customer.is_active is False


def test_rotas_de_clientes_exigem_login(anonymous_client):
    for path in ("/customers/", "/customers/novo", "/customers/1", "/customers/1/editar"):
        response = anonymous_client.get(path)
        assert response.status_code == 302
        assert response.headers["Location"].split("?", 1)[0].endswith("/login")
