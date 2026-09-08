from sqlalchemy import BigInteger, Column, DateTime, ForeignKey
from sqlalchemy.sql import func

from app.database import Base


class LojaEstiloMusical(Base):
    __tablename__ = "lojaestilomusical"

    loja_id = Column(
        BigInteger,
        ForeignKey("loja.loja_id", ondelete="CASCADE", onupdate="CASCADE"),
        primary_key=True,
    )
    organizacaoestilomusical_id = Column(
        BigInteger,
        ForeignKey(
            "organizacaoestilomusical.organizacaoestilomusical_id",
            ondelete="CASCADE",
            onupdate="CASCADE",
        ),
        primary_key=True,
    )
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
