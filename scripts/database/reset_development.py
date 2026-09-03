"""Apaga e recria um banco após confirmação explícita do ambiente e do nome."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql
from pymysql.constants import CLIENT

PROJECT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_DIR))

from app.core.config import APP_ENV, DATABASE_URL


BASE_DIR = Path(__file__).resolve().parent
DROP_SQL = BASE_DIR / "drop" / "drop_schema.sql"
CREATE_SQL = BASE_DIR / "create" / "create_schema.sql"


def _connection_config() -> dict[str, object]:
    parsed = urlparse(DATABASE_URL or "")
    database = unquote((parsed.path or "").lstrip("/"))
    if not parsed.hostname or not database:
        raise RuntimeError("DATABASE_URL inválida ou sem nome do banco")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "database": database,
        "charset": "utf8mb4",
        "autocommit": False,
        "client_flag": CLIENT.MULTI_STATEMENTS,
    }


def _execute_script(cursor: pymysql.cursors.Cursor, path: Path) -> None:
    cursor.execute(path.read_text(encoding="utf-8"))
    while cursor.nextset():
        pass


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--confirm-database",
        required=True,
        help="Nome exato do banco que será apagado e recriado",
    )
    parser.add_argument(
        "--allow-production",
        action="store_true",
        help="Autoriza explicitamente a recriação do banco de produção",
    )
    args = parser.parse_args()

    config = _connection_config()
    database = str(config["database"])
    is_production = APP_ENV in {"prod", "production"}
    if APP_ENV not in {"dev", "development", "prod", "production"}:
        raise RuntimeError(f"Reset bloqueado para APP_ENV={APP_ENV!r}")
    if is_production and not args.allow_production:
        raise RuntimeError("Reset de produção exige --allow-production")
    if args.confirm_database != database:
        raise RuntimeError(
            "Confirmação não corresponde ao banco configurado: "
            f"esperado {database!r}"
        )
    expected_marker = "prod" if is_production else "dev"
    if expected_marker not in database.lower():
        raise RuntimeError(
            f"Reset bloqueado: o banco {database!r} não corresponde ao ambiente {APP_ENV!r}"
        )

    connection = pymysql.connect(**config)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            active_database = cursor.fetchone()[0]
            if active_database != database:
                raise RuntimeError(
                    f"Banco ativo inesperado: {active_database!r}; esperado {database!r}"
                )

            print(f"Recriando banco: {database}")
            _execute_script(cursor, DROP_SQL)
            _execute_script(cursor, CREATE_SQL)
            connection.commit()

            cursor.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema = DATABASE()"
            )
            table_count = cursor.fetchone()[0]
            cursor.execute(
                "SELECT column_name, is_nullable FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'itvenda' "
                "AND column_name IN ('tipoitem', 'produto_id', 'lote_id') "
                "ORDER BY column_name"
            )
            columns = cursor.fetchall()
            cursor.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name IN "
                "('leadestabelecimento', 'leadestabelecimentocontrato', 'titularfinanceiro') "
                "ORDER BY table_name"
            )
            onboarding_tables = [item[0] for item in cursor.fetchall()]
            print(f"Tabelas criadas: {table_count}")
            print(f"Contrato itvenda: {columns}")
            print(f"Tabelas de onboarding: {onboarding_tables}")
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()
