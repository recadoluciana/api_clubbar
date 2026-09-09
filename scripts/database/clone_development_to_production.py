from __future__ import annotations

import os
from urllib.parse import urlparse

from sqlalchemy import create_engine, text


SOURCE_URL = os.environ["SOURCE_DATABASE_URL"]
TARGET_URL = os.environ["TARGET_DATABASE_URL"]


def database_name(url: str) -> str:
    return urlparse(url).path.strip("/")


def sqlalchemy_url(url: str) -> str:
    return url.replace("mysql://", "mysql+pymysql://", 1)


def table_names(connection) -> list[str]:
    return [
        row[0]
        for row in connection.execute(text("SHOW FULL TABLES WHERE Table_type = 'BASE TABLE'"))
    ]


def main() -> None:
    source_name = database_name(SOURCE_URL)
    target_name = database_name(TARGET_URL)
    if source_name != "clubbar_dev":
        raise RuntimeError(f"Origem inesperada: {source_name}")
    if target_name != "clubbar_prod":
        raise RuntimeError(f"Destino inesperado: {target_name}")
    if urlparse(SOURCE_URL).hostname == urlparse(TARGET_URL).hostname:
        raise RuntimeError("Origem e destino apontam para o mesmo host")

    source_engine = create_engine(sqlalchemy_url(SOURCE_URL), pool_pre_ping=True)
    target_engine = create_engine(sqlalchemy_url(TARGET_URL), pool_pre_ping=True)

    with source_engine.connect() as source, target_engine.begin() as target:
        source_tables = table_names(source)
        target_tables = table_names(target)
        if not source_tables:
            raise RuntimeError("A origem não possui tabelas")
        if os.getenv("CLONE_DRY_RUN") == "1":
            print(f"Origem confirmada: {source_name}, {len(source_tables)} tabelas")
            print(f"Destino confirmado: {target_name}, {len(target_tables)} tabelas atuais")
            if set(source_tables) == set(target_tables):
                count_sql = " UNION ALL ".join(
                    f"SELECT '{table}' AS tabela, COUNT(*) AS quantidade FROM `{table}`"
                    for table in source_tables
                )
                source_counts = dict(source.execute(text(count_sql)).all())
                target_counts = dict(target.execute(text(count_sql)).all())
                source_total = sum(source_counts.values())
                target_total = sum(target_counts.values())
                divergencias = [
                    table
                    for table in source_tables
                    if source_counts[table] != target_counts[table]
                ]
                print(f"Registros: origem={source_total}, destino={target_total}")
                print(f"Tabelas com contagem divergente: {len(divergencias)}")
            return

        target.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        for table in target_tables:
            target.execute(text(f"DROP TABLE IF EXISTS `{table}`"))

        # FOREIGN_KEY_CHECKS=0 permite recriar as definições idênticas às da origem
        # mesmo quando uma chave aponta para tabela criada posteriormente.
        for table in source_tables:
            create_sql = source.execute(text(f"SHOW CREATE TABLE `{table}`")).one()[1]
            target.execute(text(create_sql))

        copied_rows = 0
        for table in source_tables:
            columns = [
                row[0]
                for row in source.execute(text(f"SHOW COLUMNS FROM `{table}`"))
                if "GENERATED" not in str(row[5]).upper()
                or str(row[5]).upper() == "DEFAULT_GENERATED"
            ]
            quoted_columns = ", ".join(f"`{column}`" for column in columns)
            placeholders = ", ".join(["%s"] * len(columns))
            insert_sql = f"INSERT INTO `{table}` ({quoted_columns}) VALUES ({placeholders})"
            result = source.execution_options(stream_results=True).execute(
                text(f"SELECT {quoted_columns} FROM `{table}`")
            )
            while True:
                rows = result.fetchmany(500)
                if not rows:
                    break
                target.exec_driver_sql(insert_sql, [tuple(row) for row in rows])
                copied_rows += len(rows)

        target.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        final_tables = table_names(target)
        if len(final_tables) != len(source_tables):
            raise RuntimeError("Quantidade de tabelas copiada não confere")
        print(f"Cópia concluída: {len(final_tables)} tabelas e {copied_rows} registros")


if __name__ == "__main__":
    main()
