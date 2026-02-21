from sqlalchemy import Column, BigInteger, String, DateTime, ForeignKeyConstraint, func, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base  # ajuste se necessário


class Cidade(Base):
    __tablename__ = "cidade"

    cidade_id = Column(BigInteger, primary_key=True, autoincrement=True)

    pais_id = Column(BigInteger, nullable=False)
    estado_id = Column(BigInteger, nullable=False)

    nmcidade = Column(String(120), nullable=False)

    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())

    __table_args__ = (
        # ✅ FK composta: garante que cidade.pais_id = estado.pais_id
        ForeignKeyConstraint(
            ["pais_id", "estado_id"],
            ["estado.pais_id", "estado.estado_id"],
            ondelete="RESTRICT",
            onupdate="CASCADE",
            name="fk_cidade_estado_pais",
        ),
        UniqueConstraint("estado_id", "nmcidade", name="uk_cidade_estado_nome"),
    )

    pais = relationship("Pais", back_populates="cidades")
    estado = relationship("Estado", back_populates="cidades")
