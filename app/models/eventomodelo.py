from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.sql import func
from app.database import Base

class EventoModelo(Base):
    __tablename__ = "eventomodelo"
    eventomodelo_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id"), nullable=False, index=True)
    nmtituloevento = Column(String(120), nullable=False)
    dsdescevento = Column(Text)
    dspoliticacancelamento = Column(Text)
    dspoliticareembolso = Column(Text)
    dspoliticacashback = Column(Text)
    nmlocalevento = Column(String(120))
    dsendlocevento = Column(String(200))
    urlbannerevento = Column(String(255))
    urlmapaingressos = Column(String(255))
    dsmapaingressos = Column(String(255))
    vrprecolote = Column(Numeric(10, 2), nullable=False, server_default="0")
    qttotallote = Column(Integer)
    statusevento = Column(Enum("ATIVO", "INATIVO", name="eventomodelo_status"), nullable=False, server_default="ATIVO")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())
