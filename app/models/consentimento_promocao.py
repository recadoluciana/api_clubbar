from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class ConsentimentoPromocao(Base):
    __tablename__ = "consentimento_promocao"
    __table_args__ = (UniqueConstraint("cliente_id", "loja_id", name="uq_consentimento_promocao_cliente_loja"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    cliente_id = Column(BigInteger, ForeignKey("cliente.cliente_id", ondelete="CASCADE"), nullable=False, index=True)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id", ondelete="CASCADE"), nullable=False, index=True)
    push = Column(Boolean, nullable=False, default=False, server_default="0")
    email = Column(Boolean, nullable=False, default=False, server_default="0")
    atualizado_em = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
