from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    String,
    text,
)
from sqlalchemy.sql import func

from app.database import Base


class Organizacao(Base):
    __tablename__ = "organizacao"

    organizacao_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )

    nmorganizacao = Column(
        String(120),
        nullable=False,
        index=True,
    )

    rzsocialorganizacao = Column(
        String(160),
        nullable=False,
    )

    cnpjorganizacao = Column(
        String(14),
        nullable=False,
        unique=True,
    )

    emailorganizacao = Column(
        String(255),
        nullable=False,
    )

    telorganizacao = Column(
        String(25),
        nullable=False,
    )

    ceporganizacao = Column(
        String(20),
        nullable=True,
    )

    endorganizacao = Column(
        String(255),
        nullable=False,
    )

    nrendorganizacao = Column(
        String(20),
        nullable=False,
    )

    complorganizacao = Column(
        String(120),
        nullable=True,
    )

    estado_id = Column(
        BigInteger,
        ForeignKey(
            "estado.estado_id",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=False,
    )

    cidade_id = Column(
        BigInteger,
        ForeignKey("cidade.cidade_id"),
        nullable=False,
        index=True,
    )

    nmbairro = Column(
        String(120),
        nullable=True,
    )

    sitorganizacao = Column(
        String(15),
        nullable=False,
        server_default=text("'ATIVA'"),
        index=True,
    )

    leadparceiro_id = Column(
        BigInteger,
        ForeignKey(
            "leadparceiro.leadparceiro_id",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        nullable=True,
        unique=True,
        index=True,
    )

    dtcriacao = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    dtultatu = Column(
        DateTime,
        nullable=True,
        onupdate=func.now(),
    )