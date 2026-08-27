from sqlalchemy import (
    Column, BigInteger, String, DateTime, Enum
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class Evento(Base):
    __tablename__ = "evento"

    evento_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organizacao_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False)

    nmtituloevento = Column(String(120), nullable=False)
    dtinicioevento = Column(DateTime, nullable=False)
    dtfimevento = Column(DateTime, nullable=True)

    nmlocalevento = Column(String(120), nullable=True)
    dsendlocevento = Column(String(200), nullable=True)
    urlbannerevento = Column(String(255), nullable=True)

    statusevento = Column(
        Enum("RASCUNHO", "ATIVO", "ENCERRADO", "CANCELADO", name="evento_statusevento"),
        nullable=False,
        server_default="RASCUNHO",
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
    atracoes = relationship("EventoAtracao", back_populates="evento", cascade="all, delete-orphan")
    detalhes = relationship(
        "EventoDescricao",
        back_populates="evento",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    def _obter_texto(self, campo):
        return getattr(self.detalhes, campo, None) if self.detalhes else None

    def _definir_texto(self, campo, valor):
        if self.detalhes is None:
            from app.models.eventodescricao import EventoDescricao
            self.detalhes = EventoDescricao()
        setattr(self.detalhes, campo, valor)

    dsdescevento = property(
        lambda self: self._obter_texto("dsdescevento"),
        lambda self, valor: self._definir_texto("dsdescevento", valor),
    )
    dspoliticacancelamento = property(
        lambda self: self._obter_texto("dspoliticacancelamento"),
        lambda self, valor: self._definir_texto("dspoliticacancelamento", valor),
    )
    dspoliticareembolso = property(
        lambda self: self._obter_texto("dspoliticareembolso"),
        lambda self, valor: self._definir_texto("dspoliticareembolso", valor),
    )
    dspoliticacashback = property(
        lambda self: self._obter_texto("dspoliticacashback"),
        lambda self, valor: self._definir_texto("dspoliticacashback", valor),
    )


from app.models.eventodescricao import EventoDescricao  # noqa: E402,F401
