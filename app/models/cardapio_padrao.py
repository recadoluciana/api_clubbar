from sqlalchemy import BigInteger, Column, DateTime, DECIMAL, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class CardapioPadraoCategoria(Base):
    __tablename__ = "cardapio_padrao_categoria"

    cardapio_padrao_categoria_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True)
    nmcategoria = Column(String(120), nullable=False)
    sitcategoria = Column(String(10), nullable=False, default="ATIVA")
    idordcategoria = Column(BigInteger, nullable=False, default=1)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("organizacao_id", "nmcategoria", name="uk_cardapio_padrao_categoria_nome"),
    )


class CardapioPadraoProduto(Base):
    __tablename__ = "cardapio_padrao_produto"

    cardapio_padrao_produto_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True)
    cardapio_padrao_categoria_id = Column(
        BigInteger,
        ForeignKey("cardapio_padrao_categoria.cardapio_padrao_categoria_id"),
        nullable=True,
        index=True,
    )
    nmproduto = Column(String(100), nullable=False)
    dsproduto = Column(String(255), nullable=True)
    vrprecoprod = Column(DECIMAL(10, 2), nullable=False)
    sitproduto = Column(String(10), nullable=False, default="ATIVO")
    urlfotoproduto = Column(String(255), nullable=True)
    tipodesconto = Column(String(15), nullable=False, default="NENHUM")
    vrdesconto = Column(DECIMAL(10, 2), nullable=False, default=0)
    pccashback = Column(DECIMAL(10, 2), nullable=True)
    dtinidesconto = Column(DateTime, nullable=True)
    dtfimdesconto = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("organizacao_id", "nmproduto", name="uk_cardapio_padrao_produto_nome"),
    )
