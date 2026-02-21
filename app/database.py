# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.engine import URL

from app.core.config import MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username = MYSQL_USER,
    password = MYSQL_PASSWORD,   # pode ter @ que funciona
    host     = MYSQL_HOST,
    port     = int(MYSQL_PORT),
    database = MYSQL_DB,
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()