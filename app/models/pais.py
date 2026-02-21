from sqlalchemy import Column, BigInteger, String, DateTime, func
from sqlalchemy.orm import relationship

from app.database import Base  # ajuste se seu Base estiver em outro lugar


class Pais(Base):
    __tablename__ = "pais"

    pais_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cdpais = Column(BigInteger, nullable=False, unique=True)
    nmpais = Column(String(120), nullable=False, unique=True)
    sgpais = Column(String(5), nullable=True)

    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())

    estados = relationship("Estado", back_populates="pais", cascade="all, delete-orphan")
    cidades = relationship("Cidade", back_populates="pais", cascade="all, delete-orphan")
