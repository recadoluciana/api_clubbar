from sqlalchemy import Column, BigInteger, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class Carrinho(Base):
    __tablename__ = "carrinho"

    carrinho_id    = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, nullable=False, index=True)
    loja_id        = Column(BigInteger, nullable=False)
    cliente_id     = Column(BigInteger, nullable=False, index=True)
    dtcriacao      = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    dtultatu       = Column(DateTime, onupdate=func.current_timestamp(), nullable=True)
