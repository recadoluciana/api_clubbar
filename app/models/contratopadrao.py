from sqlalchemy import BigInteger, Column, DateTime, Numeric, String, Text, text

from app.database import Base


class ContratoPadrao(Base):
    __tablename__ = "contratopadrao"

    contratopadrao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    versao = Column(String(30), nullable=False, unique=True)
    titulo = Column(String(160), nullable=False)
    conteudomodelo = Column(Text, nullable=False)
    vrimplantacao = Column(Numeric(10, 2), nullable=False, server_default="0")
    sitcontrato = Column(String(10), nullable=False, server_default="ATIVO", index=True)
    operador_id = Column(BigInteger, nullable=True)
    dtvigencia = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))
