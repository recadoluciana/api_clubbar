from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, UniqueConstraint, CHAR
from sqlalchemy.sql import func
from app.database import Base

class Loja(Base):
    __tablename__ = "loja"

    loja_id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True)

    nmloja = Column(String(120), nullable=False)
    endloja = Column(String(255))
    sitloja = Column(String(15), nullable=False, default="ATIVA")
    
    nrdiavalidade = Column(BigInteger,nullable=False, default=90)

    dshorarioloja = Column(String(255))
    aberto24x7 = Column(CHAR(1), nullable=False, default="N")
    nrtelloja = Column(String(25))

    dtcriacao = Column(DateTime, server_default=func.now(), nullable=False)
    dtultatu = Column(DateTime, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("organizacao_id", "loja_id", name="uq_loja_org_loja"),
    )
