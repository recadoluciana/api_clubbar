#leadagendamento.py
from sqlalchemy import BigInteger, Column, DateTime, Enum, ForeignKey, String
from sqlalchemy.sql import func

from app.database import Base


class LeadAgendamento(Base):
    __tablename__ = "leadagendamento"

    leadagendamento_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    leadparceiro_id = Column(
        BigInteger,
        ForeignKey("leadparceiro.leadparceiro_id"),
        nullable=False,
        index=True,
    )
    tipo = Column(
        Enum(
            "DEMONSTRACAO",
            "LIGACAO",
            "REUNIAO_ONLINE",
            "VISITA",
            name="enum_leadagendamento_tipo",
        ),
        nullable=False,
    )
    dtagendamento = Column(DateTime, nullable=False)
    observacao = Column(String(500), nullable=True)
    status = Column(
        Enum(
            "PENDENTE",
            "CONFIRMADO",
            "RECUSADO",
            "REALIZADO",
            "CANCELADO",
            name="enum_leadagendamento_status",
        ),
        nullable=False,
        server_default="PENDENTE",
    )
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())