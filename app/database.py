from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker, declarative_base
from app.core.config import DATABASE_URL

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL não configurado")

# Railway pode fornecer mysql://..., então garantimos pymysql
db_url = DATABASE_URL.replace("mysql://", "mysql+pymysql://", 1)

engine = create_engine(
    db_url,
    pool_pre_ping=True,
    future=True,
)

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
