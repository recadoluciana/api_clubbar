from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base  # ajuste se necessário


class Estado(Base):
    __tablename__ = "estado"

    estado_id = Column(BigInteger, primary_key=True, autoincrement=True)
    pais_id = Column(BigInteger, ForeignKey("pais.pais_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)

    sgestado = Column(String(5), nullable=False)   # MG, SP...
    nmestado = Column(String(120), nullable=False)

    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint("pais_id", "sgestado", name="uk_estado_pais_sigla"),
        UniqueConstraint("pais_id", "estado_id", name="uk_estado_pais_estadoid"),  # p/ FK composta da cidade
    )

