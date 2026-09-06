from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, Text, text

from app.database import Base


class LeadEstabelecimentoContrato(Base):
    __tablename__ = "leadestabelecimentocontrato"

    leadestabelecimentocontrato_id = Column(BigInteger, primary_key=True, autoincrement=True)
    leadestabelecimento_id = Column(
        BigInteger,
        ForeignKey("leadestabelecimento.leadestabelecimento_id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
        index=True,
    )
    titularfinanceiro_id = Column(
        BigInteger,
        ForeignKey("titularfinanceiro.titularfinanceiro_id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=True,
    )
    contratopadrao_id = Column(
        BigInteger,
        ForeignKey("contratopadrao.contratopadrao_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    versao = Column(String(30), nullable=False)
    status = Column(String(20), nullable=False, server_default="RASCUNHO")
    vrtaxaprod = Column(Numeric(10, 2), nullable=False, server_default="5")
    vrtaxaing = Column(Numeric(10, 2), nullable=False, server_default="5")
    conteudocontrato = Column(Text, nullable=False)
    hashdocumento = Column(String(64), nullable=True)
    nmsignatario = Column(String(160), nullable=True)
    cpfcnpjsignatario = Column(String(14), nullable=True)
    ipaceite = Column(String(45), nullable=True)
    dtaceite = Column(DateTime, nullable=True)
    dtdisponibilizacao = Column(DateTime, nullable=True)
    dtinicio = Column(DateTime, nullable=True)
    dtfim = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))
