from sqlalchemy import Column, BigInteger, String, DateTime, Enum, DECIMAL, ForeignKey, text
from sqlalchemy.sql import func
from app.database import Base

class Produto(Base):
    __tablename__ = "produto"

    produto_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, nullable=False, index=True)
    loja_id = Column(BigInteger, nullable=False)
    categoria_id = Column(BigInteger, ForeignKey("categoria.categoria_id"), nullable=True)
    nmproduto = Column(String(100), nullable=False)
    dsproduto = Column(String(255), nullable=True)
    vrprecoprod = Column(DECIMAL(10, 2), nullable=False)
    sitproduto = Column(Enum("ATIVO", "INATIVO", name="sitproduto_enum"), nullable=False, server_default="ATIVO")
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(
        DateTime,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP"),
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )
    idtipoproduto = Column(Enum("I", "P", name="idtipoproduto_enum"), nullable=False, server_default="P")
    lote_id = Column(BigInteger, nullable=True)

    urlfotoproduto = Column(String(255), nullable=True)

    tipodesconto = Column(
        Enum("NENHUM", "PERCENTUAL", "VALOR", name="enum_tipodesconto_produto"),
        nullable=False,
        default="NENHUM",
    )

    vrdesconto = Column(DECIMAL(10, 2), nullable=False, default=0.00)

    dtinidesconto = Column(DateTime, nullable=True)
    dtfimdesconto = Column(DateTime, nullable=True)