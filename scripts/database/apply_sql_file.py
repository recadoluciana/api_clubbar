import os
import sys
from pathlib import Path

from sqlalchemy import create_engine


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Uso: python apply_sql_file.py caminho/migracao.sql")

    database_url = (
        os.getenv("MYSQL_PUBLIC_URL") or os.getenv("DATABASE_PUBLIC_URL") or os.environ["DATABASE_URL"]
    ).replace("mysql://", "mysql+pymysql://", 1)
    engine = create_engine(database_url, pool_pre_ping=True)
    sql = Path(sys.argv[1]).read_text(encoding="utf-8")
    statements = [item.strip() for item in sql.split(";") if item.strip()]
    try:
        with engine.begin() as connection:
            for statement in statements:
                connection.exec_driver_sql(statement)
        print(f"Migração aplicada: {len(statements)} comandos.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
