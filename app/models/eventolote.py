from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, literal, select
from sqlalchemy.orm import column_property, relationship, synonym
from sqlalchemy.sql import func

from app.database import Base
from app.models.eventoloteglobal import EventoLoteGlobal


class EventoLote(Base):
    """Configuração de um setor dentro de um lote global.

    O nome da classe é mantido apenas para compatibilidade com o checkout e
    relatórios. A tabela física não é a estrutura antiga ``eventolote``.
    """

    __tablename__ = "eventolotesetor"

    lote_id = Column(BigInteger, primary_key=True, autoincrement=True)

    loteglobal_id = Column(
        BigInteger,
        ForeignKey("eventoloteglobal.loteglobal_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    eventosetor_id = Column(
        BigInteger,
        ForeignKey("eventosetor.eventosetor_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    # Meta comercial opcional. Nulo significa vender todo o saldo do setor.
    qtlimite = Column(Integer, nullable=True)
    qtvendidalote = Column(Integer, nullable=False, server_default="0")
    situacao = Column(String(10), nullable=False, server_default="ATIVO")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())

    lote_global = relationship("EventoLoteGlobal", back_populates="configuracoes_setor")
    setor = relationship("EventoSetor")
    precos = relationship(
        "EventoLotePreco",
        cascade="all, delete-orphan",
        order_by="EventoLotePreco.nrordem",
    )

    # Projeções somente de leitura para os pontos ainda compartilhados por
    # checkout, reservas e relatórios. Os dados continuam normalizados no
    # lote global; não há duplicação dessas colunas em eventolotesetor.
    organizacao_id = column_property(
        select(EventoLoteGlobal.organizacao_id)
        .where(EventoLoteGlobal.loteglobal_id == loteglobal_id)
        .correlate_except(EventoLoteGlobal)
        .scalar_subquery()
    )
    loja_id = column_property(
        select(EventoLoteGlobal.loja_id)
        .where(EventoLoteGlobal.loteglobal_id == loteglobal_id)
        .correlate_except(EventoLoteGlobal)
        .scalar_subquery()
    )
    evento_id = column_property(
        select(EventoLoteGlobal.evento_id)
        .where(EventoLoteGlobal.loteglobal_id == loteglobal_id)
        .correlate_except(EventoLoteGlobal)
        .scalar_subquery()
    )
    nrlote = column_property(
        select(EventoLoteGlobal.nrlote)
        .where(EventoLoteGlobal.loteglobal_id == loteglobal_id)
        .correlate_except(EventoLoteGlobal)
        .scalar_subquery()
    )
    nmlote = column_property(
        select(EventoLoteGlobal.nmlote)
        .where(EventoLoteGlobal.loteglobal_id == loteglobal_id)
        .correlate_except(EventoLoteGlobal)
        .scalar_subquery()
    )
    dtiniciovenda = column_property(
        select(EventoLoteGlobal.dtiniciovenda)
        .where(EventoLoteGlobal.loteglobal_id == loteglobal_id)
        .correlate_except(EventoLoteGlobal)
        .scalar_subquery()
    )
    dtfimvenda = column_property(
        select(EventoLoteGlobal.dtfimvenda)
        .where(EventoLoteGlobal.loteglobal_id == loteglobal_id)
        .correlate_except(EventoLoteGlobal)
        .scalar_subquery()
    )
    statuslote = column_property(
        select(EventoLoteGlobal.situacao)
        .where(EventoLoteGlobal.loteglobal_id == loteglobal_id)
        .correlate_except(EventoLoteGlobal)
        .scalar_subquery()
    )
    qttotallote = synonym("qtlimite")
    usarcapacidaderestante = column_property(literal("N"))

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
