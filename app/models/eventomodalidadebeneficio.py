from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.sql import func

from app.database import Base


class EventoModalidadeBeneficio(Base):
    __tablename__ = "eventomodalidadebeneficio"

    evento_id = Column(BigInteger, ForeignKey("evento.evento_id", ondelete="CASCADE"), nullable=False)
    modalidade_id = Column(BigInteger, ForeignKey("modalidadeingresso.modalidade_id", ondelete="RESTRICT"), nullable=False)
    beneficio_id = Column(BigInteger, ForeignKey("beneficioingresso.beneficio_id", ondelete="RESTRICT"), nullable=False)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    __table_args__ = (PrimaryKeyConstraint("evento_id", "modalidade_id", "beneficio_id"),)
