# app/models/venda.py
from sqlalchemy import (
    BigInteger, Column, DateTime, Enum, ForeignKey, Numeric
)
from sqlalchemy.sql import func

from app.database import Base


class Venda(Base):
    __tablename__ = "venda"

    venda_id = Column(BigInteger, primary_key=True, autoincrement=True)

    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False)
    cliente_id = Column(BigInteger, ForeignKey("cliente.cliente_id", ondelete="SET NULL", onupdate="CASCADE"), nullable=True)

    dsplataforma = Column(Enum("ANDROID", "TOTEM", "IOS", "OUTROS", name="dsplataforma_enum"), nullable=False, server_default="OUTROS")
    sitvenda = Column(Enum("ABERTA", "PAGA", "CANCELADA", name="sitvenda_enum"), nullable=False, server_default="ABERTA")

    totalvenda = Column(Numeric(10, 2), nullable=False, server_default="0")

    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())
