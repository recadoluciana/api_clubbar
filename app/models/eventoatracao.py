from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class EventoAtracao(Base):
    __tablename__ = "eventoatracao"
    eventoatracao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    evento_id = Column(BigInteger, ForeignKey("evento.evento_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    atracao_id = Column(BigInteger, ForeignKey("atracao.atracao_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    dtinicioatracao = Column(DateTime, nullable=False)
    dtfimatracao = Column(DateTime, nullable=False)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, onupdate=func.now())
    evento = relationship("Evento", back_populates="atracoes")
    atracao = relationship("Atracao", back_populates="eventos")
    __table_args__ = (UniqueConstraint("evento_id", "atracao_id", "dtinicioatracao", name="uq_eventoatracao_evento_atracao_inicio"),)
