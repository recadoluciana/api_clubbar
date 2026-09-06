from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, Text, text

from app.database import Base


class CobrancaImplantacao(Base):
    __tablename__ = "cobrancaimplantacao"

    cobrancaimplantacao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    leadestabelecimentocontrato_id = Column(BigInteger, ForeignKey("leadestabelecimentocontrato.leadestabelecimentocontrato_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, unique=True)
    leadestabelecimento_id = Column(BigInteger, ForeignKey("leadestabelecimento.leadestabelecimento_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=True, index=True)
    valor = Column(Numeric(10, 2), nullable=False)
    status = Column(String(15), nullable=False, server_default="PENDENTE", index=True)
    asaas_checkout_id = Column(String(100), nullable=True, unique=True)
    asaas_payment_id = Column(String(100), nullable=True, unique=True)
    asaas_checkout_url = Column(Text, nullable=True)
    billing_type = Column(String(30), nullable=True)
    external_reference = Column(String(100), nullable=False, unique=True)
    justificativaisencao = Column(String(500), nullable=True)
    operadorisencao_id = Column(BigInteger, nullable=True)
    dtvencimento = Column(DateTime, nullable=True)
    dtpagamento = Column(DateTime, nullable=True)
    dtisencao = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))
