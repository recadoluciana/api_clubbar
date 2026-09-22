from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class PoliticaCompra(Base):
    __tablename__ = "politicacompra"
    __table_args__ = (UniqueConstraint("tipopolitica", "versao", name="uq_politicacompra_tipo_versao"),)

    politicacompra_id = Column(BigInteger, primary_key=True, autoincrement=True)
    versao = Column(String(30), nullable=False)
    # A versao e unica dentro do tipo; a restricao composta fica na migration.
    tipopolitica = Column(String(20), nullable=False, server_default="INGRESSO")
    titulo = Column(String(160), nullable=False)
    conteudo = Column(Text, nullable=False)
    qtd_dias_cancelamento = Column(Integer, nullable=True)
    qtd_horas_antecedencia_cancelamento = Column(Integer, nullable=True)
    qtd_alteracoes_participante = Column(Integer, nullable=True)
    qtd_horas_antecedencia_alteracao = Column(Integer, nullable=True)
    sitpolitica = Column(String(20), nullable=False, server_default="RASCUNHO")
    operador_id = Column(BigInteger, ForeignKey("operador.operador_id"), nullable=True)
    dtiniciovigencia = Column(DateTime, nullable=True)
    dtfimvigencia = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
