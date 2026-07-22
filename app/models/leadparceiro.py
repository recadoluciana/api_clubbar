# app/models/leadparceiro.py

import enum

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    text,
)

from app.database import Base


class StatusLeadParceiro(str, enum.Enum):
    NOVO = "NOVO"
    CONTATADO = "CONTATADO"
    NEGOCIANDO = "NEGOCIANDO"
    CONVERTIDO = "CONVERTIDO"
    PERDIDO = "PERDIDO"


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

    nmestabelecimento = Column(
        String(160),
        nullable=False,
    )

    tipo = Column(
        String(30),
        nullable=False,
    )

    telefone = Column(
        String(30),
        nullable=False,
    )

    email = Column(
        String(160),
        nullable=False,
        index=True,
    )

    estado_id = Column(
        BigInteger,
        ForeignKey(
            "estado.estado_id",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    cidade_id = Column(
        BigInteger,
        ForeignKey(
            "cidade.cidade_id",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    mensagem = Column(
        Text,
        nullable=True,
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
            f"estabelecimento={self.nmestabelecimento} "
            f"status={self.status}>"
        )