from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.sql import func

from app.database import Base


class EventoModeloModalidade(Base):
    __tablename__ = "eventomodelomodalidade"

    eventomodelo_id = Column(BigInteger, ForeignKey("eventomodelo.eventomodelo_id", ondelete="CASCADE"), nullable=False)
    modalidade_id = Column(BigInteger, ForeignKey("modalidadeingresso.modalidade_id", ondelete="RESTRICT"), nullable=False)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    __table_args__ = (PrimaryKeyConstraint("eventomodelo_id", "modalidade_id"),)
