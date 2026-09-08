from sqlalchemy import (
    Column,
    BigInteger,
    String,
    Integer,
    DateTime,
    Enum,
    DECIMAL,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EventoLote(Base):
    __tablename__ = "eventolote"

    lote_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organizacao_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False)

    evento_id = Column(
        BigInteger,
        ForeignKey("evento.evento_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
    )
    eventosetor_id = Column(
        BigInteger,
        ForeignKey("eventosetor.eventosetor_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=True,
    )
    nrlote = Column(Integer, nullable=False, server_default="1")
    nmlote = Column(String(80), nullable=False)

    qttotallote = Column(Integer, nullable=True)
    usarcapacidaderestante = Column(String(1), nullable=False, server_default="N")
    qtvendidalote = Column(Integer, nullable=True)

    dtiniciovenda = Column(DateTime, nullable=True)
    dtfimvenda = Column(DateTime, nullable=True)

    statuslote = Column(
        Enum("ATIVO", "ESGOTADO", "ENCERRADO", "INATIVO", name="eventolote_statuslote"),
        nullable=False,
        server_default="ATIVO",
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

    evento = relationship("Evento")
    setor = relationship("EventoSetor")
    precos = relationship("EventoLotePreco", cascade="all, delete-orphan", order_by="EventoLotePreco.nrordem")

    @property
    def nmsetor(self):
        return self.setor.nmsetor if self.setor else None

    def __repr__(self) -> str:
        return (
            f"<EventoLote id={self.lote_id} "
            f"evento={self.evento_id} "
            f"nome={self.nmlote!r} "
            f"status={self.statuslote}>"
        )

from app.models.eventosetor import EventoSetor  # noqa: E402,F401
from app.models.eventolotepreco import EventoLotePreco  # noqa: E402,F401
