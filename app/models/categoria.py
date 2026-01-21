from sqlalchemy import Column, BigInteger, String, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Categoria(Base):
    __tablename__ = "categoria"

    categoria_id = Column(BigInteger, primary_key=True, index=True)
    organizacao_id = Column(BigInteger, nullable=False, index=True)
    loja_id = Column(BigInteger, nullable=False, index=True)

    nmcategoria = Column(String(120), nullable=False)
    sitcategoria = Column(Enum("ATIVA", "INATIVA"), nullable=False, server_default="ATIVA")

    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu  = Column(DateTime, nullable=True, onupdate=func.now())
