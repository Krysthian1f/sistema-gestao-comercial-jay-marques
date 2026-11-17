from pathlib import Path
import os
import subprocess
import sys

import pytest
from sqlalchemy import inspect

from app import create_app
from app.extensions import db
from config import _database_uri, _is_production, _secure_cookies, normalize_database_uri


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    ("configured_uri", "expected"),
    [
        (
            "postgres://owner:password@host.example:5432/jay_marques",
            "postgresql+psycopg://owner:password@host.example:5432/jay_marques",
        ),
        (
            "postgresql://owner:password@host.example:5432/jay_marques",
            "postgresql+psycopg://owner:password@host.example:5432/jay_marques",
        ),
        (
            "postgresql+psycopg://owner:password@host.example:5432/jay_marques",
            "postgresql+psycopg://owner:password@host.example:5432/jay_marques",
        ),
    ],
)
def test_normaliza_url_postgresql_do_render(monkeypatch, configured_uri, expected):
    monkeypatch.setenv("DATABASE_URL", configured_uri)

    assert _database_uri() == expected


def test_preserva_parametros_tls_na_url_neon():
    uri = "postgresql://owner:password@ep.example.neon.tech/jay?sslmode=require&channel_binding=require"

    assert normalize_database_uri(uri) == (
        "postgresql+psycopg://owner:password@ep.example.neon.tech/jay?sslmode=require&channel_binding=require"
    )


def test_sqlite_pode_apontar_para_diretorio_persistente(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SQLITE_DATA_DIR", str(tmp_path))

    assert _database_uri() == f"sqlite:///{(tmp_path / 'gestao_comercial.sqlite').as_posix()}"


def test_producao_recusa_iniciar_sem_secret_key(tmp_path: Path):
    with pytest.raises(RuntimeError, match="Configure SECRET_KEY"):
        create_app(
            {
                "IS_PRODUCTION": True,
                "SECRET_KEY": None,
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.sqlite').as_posix()}",
            }
        )


def test_producao_exige_banco_persistente(tmp_path: Path):
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        create_app(
            {
                "IS_PRODUCTION": True,
                "SECRET_KEY": "chave-de-teste",
                "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.sqlite').as_posix()}",
            }
        )


def test_producao_nao_cria_tabelas_automaticamente(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("SQLITE_DATA_DIR", str(tmp_path))
    database_path = tmp_path / "production-isolated.sqlite"
    application = create_app(
        {
            "TESTING": True,
            "IS_PRODUCTION": True,
            "SECRET_KEY": "chave-de-teste",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path.as_posix()}",
        }
    )

    try:
        with application.app_context():
            assert inspect(db.engine).get_table_names() == []
    finally:
        with application.app_context():
            db.session.remove()
            db.engine.dispose()


def test_cookie_secure_e_obrigatorio_em_producao(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "0")

    assert _secure_cookies() is True


def test_cookie_secure_pode_ser_ativado_localmente(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("SESSION_COOKIE_SECURE", "true")

    assert _secure_cookies() is True


def test_ambiente_koyeb_e_detectado_como_producao(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("RENDER", raising=False)
    monkeypatch.setenv("KOYEB_APP_NAME", "jay-marques")

    assert _is_production() is True
    assert _secure_cookies() is True


def test_script_neon_exige_database_url(monkeypatch):
    environment = os.environ.copy()
    environment.pop("DATABASE_URL", None)

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "init_neon_db.py")],
        cwd=PROJECT_ROOT,
        env=environment,
        input="",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "configure DATABASE_URL" in result.stderr


def test_script_neon_recusa_sqlite_sem_criar_ou_abrir_o_arquivo(tmp_path: Path):
    database_path = tmp_path / "nao-deve-ser-criado.sqlite"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "init_neon_db.py")],
        cwd=PROJECT_ROOT,
        env=environment,
        input="",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "SQLite e outros bancos não serão abertos" in result.stderr
    assert not database_path.exists()


def test_script_neon_recusa_database_diferente_sem_conectar():
    environment = os.environ.copy()
    environment["DATABASE_URL"] = (
        "postgresql://owner:fake-password@ep-test-pooler.c-8.aws.neon.tech/"
        "jay_marques?sslmode=require"
    )

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "init_neon_db.py")],
        cwd=PROJECT_ROOT,
        env=environment,
        input="",
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "database precisa ser neondb" in result.stderr
    assert "fake-password" not in result.stdout + result.stderr


def test_script_teste_neon_recusa_sqlite_sem_abrir_arquivo(tmp_path: Path):
    database_path = tmp_path / "nao-deve-ser-aberto.sqlite"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"

    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "testar_neon.py")],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "SQLite não será aberto" in result.stderr
    assert not database_path.exists()
