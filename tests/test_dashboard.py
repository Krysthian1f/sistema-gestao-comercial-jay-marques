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
    assert tables == []


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
        assert inspect(db.engine).get_table_names() == []

    assert "aguardando os primeiros registros" in page
    assert "Nenhuma atividade por enquanto" in page
    assert page.count('<div class="metric-value">—</div>') == 4


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
