from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.sql import func

from app.database import Base


class CheckoutAsaasDoacao(Base):
    """Fotografia imutável da campanha aplicada a um checkout Asaas."""

    __tablename__ = "checkout_asaas_doacao"

    checkoutasaasdoacao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    checkout_asaas_id = Column(
        BigInteger,
        ForeignKey("checkout_asaas.checkout_asaas_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    campanhadoacao_id = Column(
        BigInteger, ForeignKey("campanha_doacao.campanhadoacao_id"), nullable=True
    )
    nmcampanha = Column(String(120), nullable=False)
    nmbeficiario = Column(String(160), nullable=False)
    dsmensagem = Column(Text, nullable=True)
    chavepix = Column(String(160), nullable=False)
    asaas_wallet_id = Column(String(100), nullable=False)
    percentual_doacao = Column(Numeric(7, 4), nullable=False)
    split_asaas_id = Column(String(100), nullable=True, unique=True)
    situacaorepasse = Column(String(20), nullable=False, server_default="VINCULADO")
    dtliquidacao = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
