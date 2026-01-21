from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, DECIMAL
from sqlalchemy.sql import func
from app.database import Base

class Produto(Base):
    __tablename__ = "produto"

    produto_id     = Column(BigInteger, primary_key=True, index=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False)
    loja_id        = Column(BigInteger, ForeignKey("loja.loja_id"), nullable=False)
    categoria_id   = Column(BigInteger, ForeignKey("categoria.categoria_id"), nullable=False)
    nmproduto      = Column(String(100), nullable=False)
    dsproduto      = Column(String(255))
    vrprecoprod    = Column(DECIMAL(10, 2), nullable=False)
    sitproduto     = Column(String(50), nullable=False, default="ATIVO")
    skuproduto     = Column(String(100))
    dtcriacao      = Column(DateTime, server_default=func.now(), nullable=False)
    dtultatu       = Column(DateTime, onupdate=func.now())
