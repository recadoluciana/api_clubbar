from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.sql import func
from app.database import Base

class LojaPoliticaIngresso(Base):
    __tablename__ = "lojapoliticaingresso"
    lojapoliticaingresso_id = Column(BigInteger, primary_key=True, autoincrement=True)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, unique=True)
    dspoliticaingresso = Column(Text)
    urlmapaingressos = Column(String(255))
    dsmapaingressos = Column(Text)
    dsorientacoesacesso = Column(Text)
    configuracoes = Column(JSON)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, onupdate=func.now())
