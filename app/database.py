import os
import time

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from app.core.config import DATABASE_URL

# O banco e a aplicação usam o horário civil de Brasília como padrão único.
# O Railway roda em UTC; configurar o timezone do processo evita que
# datetime.now() gere valores diferentes dos defaults CURRENT_TIMESTAMP.
os.environ["TZ"] = "America/Sao_Paulo"
if hasattr(time, "tzset"):
    time.tzset()

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurado")

# Railway pode fornecer mysql://..., então garantimos pymysql
db_url = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    future=True,
)


@event.listens_for(engine, "connect")
def _configurar_timezone_brasilia(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    try:
        # Offset fixo é intencional: Brasília não usa horário de verão.
        cursor.execute("SET time_zone = '-03:00'")
    finally:
        cursor.close()

class AuditedSession(Session):
    """Sessões da aplicação; fixtures externas não recebem hooks de auditoria."""


SessionLocal = sessionmaker(
    class_=AuditedSession,
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
