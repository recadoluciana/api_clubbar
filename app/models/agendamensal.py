from sqlalchemy import BigInteger, CHAR, Column, DateTime, Enum, Integer, UniqueConstraint, text

from app.database import Base


class AgendaMensal(Base):
    __tablename__ = "agendamensal"

    agendamensal_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, nullable=False, index=True)
    loja_id = Column(BigInteger, nullable=False, index=True)
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)
    statusagenda = Column(Enum("RASCUNHO", "AGUARDANDO_ASAAS", "PUBLICADA", "INATIVA"), nullable=False, server_default="RASCUNHO")
    publicaraposaprovacao = Column(CHAR(1), nullable=False, server_default="N")
    dtpublicacao = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))

    __table_args__ = (UniqueConstraint("loja_id", "ano", "mes", name="uk_agendamensal_loja_mes"),)
