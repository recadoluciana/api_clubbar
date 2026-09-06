from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.models.atracaoestilomusical import atracao_estilo_musical


class OrganizacaoEstiloMusical(Base):
    __tablename__ = "organizacaoestilomusical"
    __table_args__ = (
        UniqueConstraint("organizacao_id", "nmestilomusical", name="uk_orgestilo_nome"),
        UniqueConstraint("organizacao_id", "estilomusical_id", name="uk_orgestilo_padrao"),
    )

    organizacaoestilomusical_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    estilomusical_id = Column(BigInteger, ForeignKey("estilomusical.estilomusical_id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True, index=True)
    nmestilomusical = Column(String(120), nullable=False)
    sitestilomusical = Column(String(10), nullable=False, server_default="ATIVO")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())

    estilo_padrao = relationship("EstiloMusical", back_populates="estilos_organizacoes")
    atracoes = relationship("Atracao", secondary=atracao_estilo_musical, back_populates="estilos")
