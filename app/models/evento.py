#evento
from sqlalchemy import (
    Column, BigInteger, String, Text, DateTime, Enum, ForeignKey
)
from sqlalchemy.orm import relationship

from app.database import Base  # ajuste se necessário


class Evento(Base):
    __tablename__ = "evento"

    evento_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organizacao_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False)

    nmtituloevento = Column(String(120), nullable=False)
    dsdescevento = Column(Text, nullable=True)

    dtinicioevento = Column(DateTime, nullable=False)
    dtfimevento = Column(DateTime, nullable=True)

    nmlocalevento = Column(String(120), nullable=True)
    dsendlocevento = Column(String(200), nullable=True)
    urlbannerevento = Column(String(255), nullable=True)

    statusevento = Column(
        Enum("RASCUNHO", "ATIVO", "ENCERRADO", "CANCELADO", name="evento_statusevento"),
        nullable=False,
        default="RASCUNHO",
    )

    dtcriacao = Column(
        DateTime,
        nullable=False,
        server_default=func.now()
    )

    dtultatu = Column(
        DateTime,
        nullable=True,
        server_default=func.now(),
        onupdate=func.now()
    )