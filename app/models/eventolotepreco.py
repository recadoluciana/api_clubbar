from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.sql import func

from app.database import Base


class EventoLotePreco(Base):
    __tablename__ = "eventolotepreco"

    lotepreco_id = Column(BigInteger, primary_key=True, autoincrement=True)
    lote_id = Column(BigInteger, ForeignKey("eventolote.lote_id", ondelete="CASCADE"), nullable=False, index=True)
    nmpreco = Column(String(100), nullable=False)
    tipopreco = Column(String(30), nullable=False, server_default="INTEIRA")
    vrpreco = Column(Numeric(10, 2), nullable=False)
    aplicacotalegal = Column(Boolean, nullable=False, server_default="0")
    exigecomprovante = Column(Boolean, nullable=False, server_default="0")
    situacao = Column(String(10), nullable=False, server_default="ATIVO")
    nrordem = Column(BigInteger, nullable=False, server_default="1")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())
