from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.sql import func

from app.database import Base


class PoliticaCompra(Base):
    __tablename__ = "politicacompra"

    politicacompra_id = Column(BigInteger, primary_key=True, autoincrement=True)
    versao = Column(String(30), nullable=False, unique=True)
    titulo = Column(String(160), nullable=False)
    conteudo = Column(Text, nullable=False)
    sitpolitica = Column(String(20), nullable=False, server_default="VIGENTE")
    operador_id = Column(BigInteger, ForeignKey("operador.operador_id"), nullable=True)
    dtiniciovigencia = Column(DateTime, nullable=True)
    dtfimvigencia = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
