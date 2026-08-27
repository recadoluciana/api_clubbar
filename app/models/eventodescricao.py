from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EventoDescricao(Base):
    __tablename__ = "eventodescricao"

    evento_id = Column(
        BigInteger,
        ForeignKey("evento.evento_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    dsdescevento = Column(Text, nullable=True)
    dspoliticacancelamento = Column(Text, nullable=True)
    dspoliticareembolso = Column(Text, nullable=True)
    dspoliticacashback = Column(Text, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())

    evento = relationship("Evento", back_populates="detalhes")
