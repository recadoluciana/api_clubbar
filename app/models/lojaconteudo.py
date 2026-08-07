from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, JSON, Text, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base

class LojaConteudo(Base):
    __tablename__ = "lojaconteudo"
    lojaconteudo_id = Column(BigInteger, primary_key=True, autoincrement=True)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, unique=True)
    dsdetalhadaloja = Column(Text)
    fotos = Column(JSON)
    publicacoes = Column(JSON)
    videos = Column(JSON)
    configuracoes = Column(JSON)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, onupdate=func.now())
