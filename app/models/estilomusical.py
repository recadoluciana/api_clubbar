from sqlalchemy import BigInteger, Column, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EstiloMusical(Base):
    __tablename__ = "estilomusical"

    estilomusical_id = Column(BigInteger, primary_key=True, autoincrement=True)
    nmestilomusical = Column(String(120), nullable=False, unique=True, index=True)
    sitestilomusical = Column(String(10), nullable=False, server_default="ATIVO")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.now())

    estilos_organizacoes = relationship("OrganizacaoEstiloMusical", back_populates="estilo_padrao")
