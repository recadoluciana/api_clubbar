from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class ClienteAsaas(Base):
    __tablename__ = "clienteasaas"

    clienteasaas_id = Column(BigInteger, primary_key=True, autoincrement=True)
    cliente_id = Column(BigInteger, ForeignKey("cliente.cliente_id", ondelete="CASCADE"), nullable=False, index=True)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id", ondelete="CASCADE"), nullable=False, index=True)
    asaas_customer_id = Column(String(100), nullable=False)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtalteracao = Column(DateTime, nullable=True, onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint("cliente_id", "loja_id", name="uq_clienteasaas_cliente_loja"),
    )
