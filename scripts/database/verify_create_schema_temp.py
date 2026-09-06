from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote, urlparse

import pymysql
from pymysql.constants import CLIENT


TEMP_DATABASE = "clubbar_schema_check"
SCHEMA = Path(__file__).resolve().parent / "create" / "create_schema.sql"


def main() -> None:
    parsed = urlparse(os.environ["DATABASE_URL"])
    config = {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "charset": "utf8mb4",
        "autocommit": True,
        "client_flag": CLIENT.MULTI_STATEMENTS,
    }
    connection = pymysql.connect(**config)
    try:
        with connection.cursor() as cursor:
            cursor.execute(f"DROP DATABASE IF EXISTS `{TEMP_DATABASE}`")
            cursor.execute(
                f"CREATE DATABASE `{TEMP_DATABASE}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            cursor.execute(f"USE `{TEMP_DATABASE}`")
            try:
                cursor.execute(SCHEMA.read_text(encoding="utf-8"))
                while cursor.nextset():
                    pass
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = %s",
                    (TEMP_DATABASE,),
                )
                print(f"Schema válido: {cursor.fetchone()[0]} tabelas")
            finally:
                cursor.execute(f"DROP DATABASE IF EXISTS `{TEMP_DATABASE}`")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
