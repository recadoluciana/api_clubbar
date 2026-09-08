from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func

from app.database import Base


class CoraDuvida(Base):
    __tablename__ = "coraduvida"

    coraduvida_id = Column(BigInteger, primary_key=True, autoincrement=True)
    pergunta = Column(String(255), nullable=False, unique=True)
    resposta = Column(Text, nullable=False)
    idordem = Column(Integer, nullable=False, server_default="0")
    sitduvida = Column(String(15), nullable=False, server_default="ATIVA", index=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())
