from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class LojaAsaas(Base):
    __tablename__ = "lojaasaas"

    lojaasaas_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id", ondelete="CASCADE"), nullable=False, index=True)
    ambiente = Column(String(20), nullable=False)
    asaas_account_id = Column(String(100), nullable=True)
    asaas_wallet_id = Column(String(100), nullable=False)
    asaas_api_key_criptografada = Column(Text, nullable=False)
    webhook_token_hash = Column(String(64), nullable=False, unique=True)
    statusintegracao = Column(String(20), nullable=False, default="ATIVA")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtalteracao = Column(DateTime, nullable=True, onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint("loja_id", "ambiente", name="uq_lojaasaas_loja_ambiente"),
    )
