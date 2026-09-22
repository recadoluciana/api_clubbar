from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String
from sqlalchemy.sql import func

from app.database import Base


class ItVendaParticipanteHistorico(Base):
    """Auditoria das transferências de titularidade de ingressos."""

    __tablename__ = "itvendaparticipantehistorico"

    historico_id = Column(BigInteger, primary_key=True, autoincrement=True)
    itvenda_id = Column(
        BigInteger,
        ForeignKey("itvenda.itvenda_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cliente_id = Column(
        BigInteger,
        ForeignKey("cliente.cliente_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    nmparticipanteanterior = Column(String(150), nullable=True)
    cpfparticipanteanterior = Column(String(11), nullable=True)
    nmparticipantenovo = Column(String(150), nullable=False)
    cpfparticipantenovo = Column(String(11), nullable=False)
    tipopreco = Column(String(30), nullable=True)
    tipobeneficio = Column(String(30), nullable=True)
    confirmoumeiaentrada = Column(Boolean, nullable=False, server_default="0")
    dttransferencia = Column(DateTime, nullable=False, server_default=func.current_timestamp())
