from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class ReservaIngressoParticipante(Base):
    __tablename__ = "reserva_ingresso_participante"

    reserva_ingresso_participante_id = Column(BigInteger, primary_key=True, autoincrement=True)
    reserva_ingresso_id = Column(BigInteger, ForeignKey("reserva_ingresso.reserva_ingresso_id", ondelete="CASCADE"), nullable=False)
    ordem = Column(Integer, nullable=False)
    nmparticipante = Column(String(150), nullable=False)
    cpfparticipante = Column(String(11), nullable=False)
    itvenda_id = Column(BigInteger, ForeignKey("itvenda.itvenda_id"), nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())

    __table_args__ = (UniqueConstraint("reserva_ingresso_id", "ordem", name="uk_reserva_participante_ordem"),)

