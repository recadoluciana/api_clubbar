from sqlalchemy import BigInteger, Column, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class EventoModeloAtracao(Base):
    __tablename__ = "eventomodeloatracao"

    eventomodeloatracao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    eventomodelo_id = Column(
        BigInteger,
        ForeignKey("eventomodelo.eventomodelo_id", ondelete="CASCADE", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    atracao_id = Column(
        BigInteger,
        ForeignKey("atracao.atracao_id", ondelete="RESTRICT", onupdate="CASCADE"),
        nullable=False,
        index=True,
    )
    ordem = Column(Integer, nullable=False, default=1)
    nrminutoinicio = Column(Integer, nullable=False, default=0)
    nrminutoduracao = Column(Integer, nullable=False, default=120)

    atracao = relationship("Atracao")

    __table_args__ = (
        UniqueConstraint("eventomodelo_id", "ordem", name="uq_eventomodeloatracao_ordem"),
    )
