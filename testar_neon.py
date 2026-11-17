"""Read-only check of the configured Neon PostgreSQL connection."""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


EXPECTED_DATABASE = "neondb"


def _diagnose_connection_error(error: Exception) -> tuple[str, str | None]:
    """Classify a database error without exposing its message or connection URL."""
    original = getattr(error, "orig", error)
    sqlstate = getattr(original, "sqlstate", None) or getattr(original, "pgcode", None)
    private_message = str(original).lower()

    if sqlstate in {"28P01", "28P02"}:
        category = "autenticação recusada; confira usuário e senha configurados localmente"
    elif sqlstate == "28000":
        category = "autorização recusada para o usuário ou conexão"
    elif sqlstate == "3D000":
        category = "banco de dados não encontrado"
    elif any(term in private_message for term in ("ssl", "tls", "certificate")):
        category = "falha na negociação ou validação de TLS"
    elif any(term in private_message for term in (
        "could not translate host",
        "name or service not known",
        "getaddrinfo failed",
        "nodename nor servname",
    )):
        category = "falha ao localizar o host (DNS ou host incorreto)"
    elif any(term in private_message for term in ("timed out", "timeout expired")):
        category = "tempo limite de conexão excedido"
    elif "connection refused" in private_message:
        category = "conexão recusada pelo host ou porta"
    elif sqlstate and sqlstate.startswith("08"):
        category = "falha de conexão com o servidor PostgreSQL"
    elif sqlstate and sqlstate.startswith("28"):
        category = "falha de autenticação ou autorização"
    elif sqlstate:
        category = "erro retornado pelo PostgreSQL"
    else:
        category = "falha de conexão ou do driver; causa não classificada"

    return category, sqlstate


def main() -> int:
    configured_url = os.environ.get("DATABASE_URL", "").strip()
    if not configured_url:
        print("Erro: defina DATABASE_URL somente nesta sessão do terminal.", file=sys.stderr)
        return 2

    if configured_url.startswith("postgres://"):
        configured_url = "postgresql+psycopg://" + configured_url.removeprefix("postgres://")
    elif configured_url.startswith("postgresql://"):
        configured_url = "postgresql+psycopg://" + configured_url.removeprefix("postgresql://")

    try:
        database_url = make_url(configured_url)
    except (TypeError, ValueError, SQLAlchemyError):
        print("Erro: DATABASE_URL não contém uma URL válida.", file=sys.stderr)
        return 2

    host = (database_url.host or "").lower()
    if database_url.get_backend_name() != "postgresql":
        print("Erro: DATABASE_URL precisa apontar para PostgreSQL; SQLite não será aberto.", file=sys.stderr)
        return 2
    if not host.endswith(".neon.tech") or "-pooler." not in host:
        print("Erro: use o host pooler do Neon terminado em .neon.tech.", file=sys.stderr)
        return 2
    if database_url.database != EXPECTED_DATABASE:
        print(f"Erro: o database da URL precisa ser {EXPECTED_DATABASE}.", file=sys.stderr)
        return 2

    engine = None
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10, "sslmode": "require"},
        )
        with engine.connect() as connection:
            database, select_result = connection.execute(
                text("SELECT current_database(), 1")
            ).one()
            # Inspect TLS on the client connection itself. pg_stat_ssl describes
            # the server-side session and can be inconclusive through a pooler.
            driver_connection = connection.connection.driver_connection
            tls_active = getattr(driver_connection.pgconn, "ssl_in_use", None)

        if database != EXPECTED_DATABASE:
            print(
                "Falha na conexão ou consulta: o servidor não retornou o database esperado; "
                "SQLSTATE indisponível.",
                file=sys.stderr,
            )
            return 1
        if tls_active is not True:
            print(
                "Falha na conexão ou consulta: TLS não foi confirmado pelo driver PostgreSQL; "
                "SQLSTATE indisponível.",
                file=sys.stderr,
            )
            return 1
        if select_result != 1:
            print(
                "Falha na conexão ou consulta: SELECT 1 retornou resultado inesperado; "
                "SQLSTATE indisponível.",
                file=sys.stderr,
            )
            return 1

        print("Conexão PostgreSQL com Neon validada.")
        print(f"Host: {database_url.host}")
        print(f"Database: {database}")
        print("TLS: ativo")
        print(f"SELECT 1: {select_result}")
        return 0
    except Exception as error:
        # Não imprimir a mensagem original: ela pode conter dados da conexão.
        category, sqlstate = _diagnose_connection_error(error)
        state_info = f"; SQLSTATE {sqlstate}" if sqlstate else "; SQLSTATE indisponível"
        print(f"Falha na conexão ou consulta: {category}{state_info}.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
