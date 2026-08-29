# app/models/leadparceiro.py

import enum

from sqlalchemy import BigInteger, Column, DateTime, Enum, String, text

from app.database import Base


class StatusLeadParceiro(str, enum.Enum):
    NOVO = "NOVO"
    CONTATADO = "CONTATADO"
    NEGOCIANDO = "NEGOCIANDO"
    ACEITOU_PARCERIA = "ACEITOU_PARCERIA"
    CONVERTIDO = "CONVERTIDO"
    RECUSOU_PARCERIA = "RECUSOU_PARCERIA"


class LeadParceiro(Base):
    __tablename__ = "leadparceiro"

    leadparceiro_id = Column(
        BigInteger,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    nmresponsavel = Column(
        String(120),
        nullable=False,
    )

    nmorganizacao = Column(String(160), nullable=True)
    
    telefone = Column(
        String(30),
        nullable=False,
    )

    email = Column(
        String(160),
        nullable=False,
        index=True,
    )

    status = Column(
        Enum(StatusLeadParceiro),
        nullable=False,
        server_default=text("'NOVO'"),
        index=True,
    )

    dtcriacao = Column(
        DateTime,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )

    dtultatu = Column(
        DateTime,
        nullable=True,
        server_onupdate=text("CURRENT_TIMESTAMP"),
    )

    def __repr__(self) -> str:
        return (
            f"<LeadParceiro "
            f"id={self.leadparceiro_id} "
            f"responsavel={self.nmresponsavel} "
            f"status={self.status}>"
        )
