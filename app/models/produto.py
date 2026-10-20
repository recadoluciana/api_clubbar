from sqlalchemy import Column, BigInteger, String, DateTime, Enum, Numeric, text
from sqlalchemy.sql import func
from app.database import Base

class Produto(Base):
    __tablename__ = "produto"

    produto_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, nullable=False, index=True)
    nmproduto = Column(String(100), nullable=False)
    dsproduto = Column(String(255), nullable=True)
    # Valor sugerido ao incluir o produto em um cardápio. O preço de venda
    # continua sendo o do CardapioItem (vrpreco), que é independente.
    vrprecopadrao = Column(
        Numeric(10, 2), nullable=False, server_default=text("5.00")
    )
    sitproduto = Column(Enum("ATIVO", "INATIVO", name="sitproduto_enum"), nullable=False, server_default="ATIVO")
    skuproduto = Column(String(100), nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    urlfotoproduto = Column(String(255), nullable=True)
