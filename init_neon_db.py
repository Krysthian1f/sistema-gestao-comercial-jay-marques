"""Create only missing application tables in the expected Neon database."""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Customer, FinancialEntry, Product, Sale, SaleItem, StockMovement, User  # noqa: F401
from config import normalize_database_uri


EXPECTED_DATABASE = "neondb"
CONFIRMATION_PHRASE = "CRIAR TABELAS NO NEON"


def main() -> int:
    if sys.argv[1:] not in ([], ["--preflight-only"]):
        print("Uso: python init_neon_db.py [--preflight-only]", file=sys.stderr)
        return 2
    preflight_only = sys.argv[1:] == ["--preflight-only"]

    configured_uri = os.environ.get("DATABASE_URL", "").strip()
    if not configured_uri:
        print("Erro: configure DATABASE_URL na sessão atual do terminal.", file=sys.stderr)
        return 2

    try:
        database_url = make_url(normalize_database_uri(configured_uri))
    except (TypeError, ValueError, SQLAlchemyError):
        print("Erro: DATABASE_URL não contém uma URL PostgreSQL válida.", file=sys.stderr)
        return 2

    host = (database_url.host or "").lower()
    sslmode = database_url.query.get("sslmode")
    if database_url.get_backend_name() != "postgresql":
        print("Operação recusada: SQLite e outros bancos não serão abertos.", file=sys.stderr)
        return 2
    if not host.endswith(".neon.tech") or "-pooler." not in host:
        print("Operação recusada: informe o host pooler de um endpoint Neon.", file=sys.stderr)
        return 2
    if database_url.database != EXPECTED_DATABASE:
        print(f"Operação recusada: o database precisa ser {EXPECTED_DATABASE}.", file=sys.stderr)
        return 2
    if str(sslmode).lower() != "require":
        print("Operação recusada: DATABASE_URL precisa incluir sslmode=require.", file=sys.stderr)
        return 2

    engine = None
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={"connect_timeout": 10, "sslmode": "require"},
        )

        # Read-only preflight: verify the actual server, client-side TLS, and schema.
        with engine.connect() as connection:
            database = connection.execute(text("SELECT current_database()")).scalar_one()
            driver_connection = connection.connection.driver_connection
            tls_active = getattr(driver_connection.pgconn, "ssl_in_use", None)
            existing_tables = set(inspect(connection).get_table_names())

        if database != EXPECTED_DATABASE:
            print("Operação recusada: o servidor retornou outro database.", file=sys.stderr)
            return 2
        if not tls_active:
            print("Operação recusada: o servidor não confirmou TLS ativo.", file=sys.stderr)
            return 2

        expected_tables = set(db.metadata.tables)
        missing_tables = expected_tables - existing_tables

        print(f"Destino validado: host={database_url.host}; database={database}; TLS ativo.")
        print(f"Tabelas esperadas ({len(expected_tables)}): {', '.join(sorted(expected_tables))}")
        print(f"Já existentes ({len(expected_tables - missing_tables)}):")
        for table_name in sorted(expected_tables - missing_tables):
            print(f"- {table_name}")
        print(f"Ausentes ({len(missing_tables)}):")
        for table_name in sorted(missing_tables):
            print(f"- {table_name}")

        if preflight_only:
            print("Pré-verificação somente leitura concluída; nenhuma alteração foi feita.")
            if missing_tables:
                print("Se autorizada, a inicialização criará somente as tabelas ausentes.")
            else:
                print("As sete tabelas já existem; nenhuma criação será necessária.")
            print("Nenhum registro será importado, apagado ou sobrescrito.")
            return 0

        if not missing_tables:
            print("O esquema já contém todas as tabelas esperadas; nenhuma alteração foi feita.")
            return 0

        print("A operação criará somente estas tabelas ausentes:")
        for table_name in sorted(missing_tables):
            print(f"- {table_name}")
        print("Nenhum registro será importado, apagado ou sobrescrito.")

        try:
            confirmation = input(
                f'Digite exatamente "{CONFIRMATION_PHRASE}" para autorizar: '
            ).strip()
        except EOFError:
            print("Operação cancelada: confirmação interativa não recebida.", file=sys.stderr)
            return 1

        if confirmation != CONFIRMATION_PHRASE:
            print("Operação cancelada; o esquema não foi alterado.")
            return 1

        # SQLAlchemy create_all creates absent tables and does not migrate or drop existing ones.
        with engine.begin() as connection:
            db.metadata.create_all(bind=connection)

        with engine.connect() as connection:
            final_tables = set(inspect(connection).get_table_names())
        still_missing = expected_tables - final_tables
        if still_missing:
            print("Falha: nem todas as tabelas esperadas foram confirmadas.", file=sys.stderr)
            return 1

        print(f"Esquema confirmado: {len(expected_tables)}/7 tabelas presentes em {database}.")
        return 0
    except Exception as error:
        # Never print an exception or URL that could contain connection credentials.
        print(f"Falha na validação ou inicialização ({type(error).__name__}).", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
