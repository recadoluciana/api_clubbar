from sqlalchemy import Column, BigInteger, Integer, String, DateTime, ForeignKey
from sqlalchemy.sql import func
from app.database import Base

class ItCarrinho(Base):
    __tablename__ = "itcarrinho"

    itcarrinho_id = Column(BigInteger, primary_key=True, autoincrement=True)
    carrinho_id = Column(BigInteger, ForeignKey("carrinho.carrinho_id"), nullable=False, index=True)
    produto_id = Column(BigInteger, ForeignKey("produto.produto_id"), nullable=False, index=True)
    qtitcarrinho = Column(Integer, nullable=False, default=1)
    dsobsitcar = Column(String(255), nullable=True)
    dtcriacao = Column(DateTime, server_default=func.current_timestamp(), nullable=False)
    dtultatu = Column(DateTime, onupdate=func.current_timestamp(), nullable=True)
