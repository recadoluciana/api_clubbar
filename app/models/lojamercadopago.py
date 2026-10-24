from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class LojaMercadoPago(Base):
    """Conexão OAuth de uma loja ao Mercado Pago.

    Nunca usamos a conta do Clubbar para receber em nome da loja: o token
    pertence à conta Mercado Pago que o parceiro autorizou para aquela loja.
    """

    __tablename__ = "lojamercadopago"

    lojamercadopago_id = Column(BigInteger, primary_key=True, autoincrement=True)
    organizacao_id = Column(BigInteger, ForeignKey("organizacao.organizacao_id"), nullable=False, index=True)
    loja_id = Column(BigInteger, ForeignKey("loja.loja_id", ondelete="CASCADE"), nullable=False, index=True)
    ambiente = Column(String(20), nullable=False)

    mercadopago_user_id = Column(String(100), nullable=True, index=True)
    public_key = Column(String(255), nullable=True)
    access_token_criptografado = Column(Text, nullable=True)
    refresh_token_criptografado = Column(Text, nullable=True)
    token_expira_em = Column(DateTime, nullable=True)

    # Estado de OAuth é armazenado apenas como hash e consumido uma vez.
    oauth_state_hash = Column(String(64), nullable=True, unique=True)
    oauth_state_expira_em = Column(DateTime, nullable=True)
    statusintegracao = Column(String(20), nullable=False, default="PENDENTE")
    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    dtalteracao = Column(DateTime, nullable=True, onupdate=func.current_timestamp())

    __table_args__ = (
        UniqueConstraint("loja_id", "ambiente", name="uq_lojamercadopago_loja_ambiente"),
    )
