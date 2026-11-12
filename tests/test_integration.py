from pathlib import Path

from app import create_app
from app.extensions import db


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
            response = client.get("/login")

        assert response.status_code == 200
        with application.app_context():
            assert Path(db.engine.url.database).resolve() == database_path.resolve()
            assert database_path.is_file()
    finally:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()


def test_sessao_com_usuario_nao_encontrado_exige_novo_login(client):
    with client.session_transaction() as session:
        session["_user_id"] = "usuario-inexistente"
        session["_fresh"] = True

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].split("?", 1)[0].endswith("/login")


def test_arquivo_css_estatico_e_servido(client):
    response = client.get("/static/css/style.css")

    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert ":root" in response.get_data(as_text=True)


def test_dashboard_recusa_metodo_post(client):
    with client.session_transaction() as session:
        token = session["csrf_token"]
    response = client.post("/", data={"csrf_token": token})

    assert response.status_code == 405


def test_rota_inexistente_responde_404(client):
    response = client.get("/rota-que-nao-existe")

    assert response.status_code == 404
