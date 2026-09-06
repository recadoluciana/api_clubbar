from sqlalchemy import Column, BigInteger, String, DateTime, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from app.database import Base

class Categoria(Base):
    __tablename__ = "categoria"

    categoria_id = Column(BigInteger, primary_key=True, index=True)
    organizacao_id = Column(BigInteger, nullable=False, index=True)
    categoriapadrao_id = Column(BigInteger, ForeignKey("categoriapadrao.categoriapadrao_id"), nullable=True)

    nmcategoria = Column(String(120), nullable=False)
    dsicone = Column(String(50), nullable=True)
    sitcategoria = Column(Enum("ATIVA", "INATIVA"), nullable=False, server_default="ATIVA")

    dtcriacao = Column(DateTime, nullable=False, server_default=func.now())
    dtultatu  = Column(DateTime, nullable=True, onupdate=func.now())

    idordcategoria = Column(
        BigInteger,
        nullable=False,
        default=1,     
    )

    __table_args__ = (
        UniqueConstraint("organizacao_id", "nmcategoria", name="uk_categoria_nome"),
        UniqueConstraint("organizacao_id", "categoriapadrao_id", name="uk_categoria_padrao_org"),
    )
