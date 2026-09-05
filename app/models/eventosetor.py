from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.database import Base


class EventoSetor(Base):
    __tablename__ = "eventosetor"

    eventosetor_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False)
    evento_id = Column(BigInteger, ForeignKey("evento.evento_id", ondelete="CASCADE"), nullable=False)
    nmsetor = Column(String(100), nullable=False)
    dssetor = Column(String(255), nullable=True)
    qtcapacidade = Column(Integer, nullable=False)
    nrordem = Column(Integer, nullable=False, server_default="1")
    sitsetor = Column(String(10), nullable=False, server_default="ATIVO")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())
