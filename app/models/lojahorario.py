from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    TIMESTAMP,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.mysql import TINYINT

from app.database import Base
from app.models.loja import Loja


class LojaHorario(Base):
    __tablename__ = "lojahorario"

    lojahorario_id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True,
    )
    loja_id = Column(
        BigInteger,
        ForeignKey(
            "loja.loja_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    diasemana = Column(TINYINT(unsigned=True), nullable=False)
    fechado = Column(Boolean, nullable=False, default=False)
    horaabertura = Column(Time, nullable=True)
    horafechamento = Column(Time, nullable=True)
    fechadiaseguinte = Column(Boolean, nullable=False, default=False)
    dtcriacao = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
    )
    dtalteracao = Column(
        TIMESTAMP,
        nullable=False,
        server_default=func.current_timestamp(),
        onupdate=func.current_timestamp(),
    )

    loja = relationship(Loja)

    __table_args__ = (
        UniqueConstraint(
            "loja_id",
            "diasemana",
            name="uq_lojahorario_dia",
        ),
        CheckConstraint(
            "diasemana BETWEEN 1 AND 7",
            name="ck_lojahorario_dia",
        ),
    )
