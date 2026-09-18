from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class CardapioModeloCategoria(Base):
    __tablename__ = "cardapiomodelocategoria"

    cardapiomodelocategoria_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True)
    cardapiomodelo_id = Column(BigInteger, ForeignKey("cardapiomodelo.cardapiomodelo_id", ondelete="CASCADE"), nullable=False, index=True)
    categoria_id = Column(BigInteger, ForeignKey("categoriaorg.categoria_id"), nullable=False)
    idordcategoria = Column(BigInteger, nullable=False, default=1)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("cardapiomodelo_id", "categoria_id", name="uk_cardapiomodelocategoria_modelo_categoria"),
    )


class CardapioModeloProduto(Base):
    __tablename__ = "cardapiomodeloproduto"

    cardapiomodeloproduto_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cardapiomodelocategoria_id = Column(BigInteger, ForeignKey("cardapiomodelocategoria.cardapiomodelocategoria_id", ondelete="CASCADE"), nullable=False, index=True)
    produto_id = Column(BigInteger, ForeignKey("produto.produto_id"), nullable=False, index=True)
    idorditem = Column(Integer, nullable=False, default=1)

    __table_args__ = (
        UniqueConstraint("cardapiomodelocategoria_id", "produto_id", name="uk_cardapiomodeloproduto_categoria_produto"),
    )


class ProdutoCategoriaOrg(Base):
    __tablename__ = "produtocategoriaorg"

    produto_id = Column(BigInteger, ForeignKey("produto.produto_id", ondelete="CASCADE"), primary_key=True)
    categoria_id = Column(BigInteger, ForeignKey("categoriaorg.categoria_id"), primary_key=True)
