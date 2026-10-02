from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EventoLoteGlobal(Base):
    """Etapa comercial única compartilhada por todos os setores do evento."""

    __tablename__ = "eventoloteglobal"
    __table_args__ = (
        UniqueConstraint("evento_id", "nrlote", name="uk_eventoloteglobal_evento_numero"),
    )

    loteglobal_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, nullable=False, index=True)
    loja_id = Column(BigInteger, nullable=False, index=True)
    evento_id = Column(
        BigInteger,
        ForeignKey("evento.evento_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    nrlote = Column(Integer, nullable=False)
    nmlote = Column(String(80), nullable=False)
    # Mantido para compatibilidade histórica. O início comercial é automático:
    # o primeiro lote acompanha a publicação e os demais começam na virada.
    dtiniciovenda = Column(DateTime, nullable=True)
    dtfimvenda = Column(DateTime, nullable=True)
    gatilhovirada = Column(String(15), nullable=False, server_default="HIBRIDO")
    situacao = Column(String(10), nullable=False, server_default="ATIVO")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())

    evento = relationship("Evento")
    configuracoes_setor = relationship(
        "EventoLote",
        cascade="all, delete-orphan",
        order_by="EventoLote.eventosetor_id",
        back_populates="lote_global",
    )
