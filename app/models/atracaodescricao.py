from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class AtracaoDescricao(Base):
    __tablename__ = "atracaodescricao"

    atracao_id = Column(
        BigInteger,
        ForeignKey("atracao.atracao_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    dsatracao = Column(Text, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())

    atracao = relationship("Atracao", back_populates="detalhes")
