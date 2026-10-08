from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.sql import func

from app.database import Base


class EventoModeloModalidadeBeneficio(Base):
    __tablename__ = "eventomodelomodalidadebeneficio"

    eventomodelo_id = Column(BigInteger, ForeignKey("eventomodelo.eventomodelo_id", ondelete="CASCADE"), nullable=False)
    modalidade_id = Column(BigInteger, ForeignKey("modalidadeingresso.modalidade_id", ondelete="RESTRICT"), nullable=False)
    beneficio_id = Column(BigInteger, ForeignKey("beneficioingresso.beneficio_id", ondelete="RESTRICT"), nullable=False)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    __table_args__ = (PrimaryKeyConstraint("eventomodelo_id", "modalidade_id", "beneficio_id"),)
