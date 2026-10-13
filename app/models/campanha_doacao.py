from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.sql import func

from app.database import Base


class CampanhaDoacao(Base):
    """Campanha opcional financiada pelo estabelecimento em cada venda."""

    __tablename__ = "campanha_doacao"

    campanhadoacao_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(
        BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True
    )
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id"), nullable=False, index=True)
    # Quando preenchido, prevalece sobre a campanha geral do estabelecimento.
    evento_id = Column(BigInteger, ForeignKey("evento.evento_id"), nullable=True, index=True)

    nmcampanha = Column(String(120), nullable=False)
    nmbeficiario = Column(String(160), nullable=False)
    urllogocampanha = Column(String(500), nullable=True)
    dsmensagem = Column(Text, nullable=True)
    chavepix = Column(String(160), nullable=False)
    asaas_wallet_id = Column(String(100), nullable=False)
    # A campanha é vinculada a uma subconta criada na conta-pai Clubbar. A
    # credencial é necessária apenas para conferir a aprovação cadastral antes
    # de liberar o split; nunca é devolvida pela API.
    asaas_account_id = Column(String(100), nullable=True)
    asaas_api_key_criptografada = Column(Text, nullable=True)
    status_asaas = Column(String(32), nullable=True)
    onboarding_url = Column(String(1000), nullable=True)
    percentual_doacao = Column(Numeric(7, 4), nullable=False)
    sitcampanha = Column(String(12), nullable=False, server_default="ATIVA")
    dtinicio = Column(DateTime, nullable=True)
    dtfim = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtultatu = Column(DateTime, nullable=True, onupdate=func.current_timestamp())
