from sqlalchemy import BigInteger, Column, DateTime, Numeric, String, text

from app.database import Base


class TaxaPadrao(Base):
    __tablename__ = "taxapadrao"

    taxapadrao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nrversao = Column(BigInteger, nullable=False, unique=True)
    pctaxaproduto = Column(Numeric(10, 2), nullable=False)
    pctaxaingresso = Column(Numeric(10, 2), nullable=False)
    vrtaxaminimaingresso = Column(Numeric(10, 2), nullable=False, server_default="0")
    sittaxapadrao = Column(String(15), nullable=False, server_default="RASCUNHO", index=True)
    dtiniciovigencia = Column(DateTime, nullable=True)
    dtfimvigencia = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))
