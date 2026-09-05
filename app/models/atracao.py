from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
from app.models.atracaoestilomusical import atracao_estilo_musical

class Atracao(Base):
    __tablename__ = "atracao"
    atracao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    nmatracao = Column(String(120), nullable=False)
    dsestilomusical = Column(String(255))
    dsatracao = Column(Text, nullable=True)
    urlbanneratracao = Column(String(255))
    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu = Column(DateTime, onupdate=func.now())
    eventos = relationship("EventoAtracao", back_populates="atracao")
    estilos = relationship(
        "EstiloMusical",
        secondary=atracao_estilo_musical,
        back_populates="atracoes",
        order_by="EstiloMusical.nmestilomusical",
    )


from app.models.estilomusical import EstiloMusical  # noqa: E402,F401
