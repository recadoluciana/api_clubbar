import os

from sqlalchemy import create_engine, text


database_url = (
    os.getenv("MYSQL_PUBLIC_URL") or os.getenv("DATABASE_PUBLIC_URL") or os.environ["DATABASE_URL"]
).replace("mysql://", "mysql+pymysql://", 1)
engine = create_engine(database_url, pool_pre_ping=True)
with engine.connect() as connection:
    tabela = connection.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema=DATABASE() AND table_name='leadestabelecimentocontrato'"
        )
    ).scalar_one()
    colunas = connection.execute(
        text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema=DATABASE() AND table_name='leadestabelecimentocontrato' "
            "AND column_name IN ('leadestabelecimentocontrato_id','conteudocontrato','dtdisponibilizacao')"
        )
    ).scalar_one()
print(f"tabela={tabela} colunas_esperadas={colunas}")
engine.dispose()
