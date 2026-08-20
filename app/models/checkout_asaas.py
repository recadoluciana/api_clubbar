#checkout_asaas.py
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, text, Numeric

from app.database import Base


class CheckoutAsaas(Base):
    __tablename__ = "checkout_asaas"

    checkout_asaas_id = Column(BigInteger, primary_key=True, autoincrement=True)

    carrinho_id = Column(BigInteger, nullable=False)
    cliente_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False)
    venda_id = Column(BigInteger, ForeignKey("venda.venda_id"), nullable=True)

    checkout_id = Column(String(100), unique=True, nullable=False)
    payment_id = Column(String(100))
    pix_qr_code_id = Column(String(100), unique=True, nullable=True)
    pix_payload = Column(Text, nullable=True)
    pix_encoded_image = Column(Text, nullable=True)
    pix_expiration_date = Column(DateTime, nullable=True)
    dsorigemconfirmacao = Column(String(20), nullable=True)
    dtconfirmacao = Column(DateTime, nullable=True)

    external_reference = Column(String(100))
    status = Column(String(30), server_default=text("'ACTIVE'"))

    checkout_url = Column(String(500), nullable=True)

    valor = Column(Numeric(10, 2), nullable=True)
    vrtaxaclubbar = Column(Numeric(10, 2), nullable=False, server_default="0")
    asaas_wallet_loja = Column(String(100), nullable=True)
    asaas_wallet_clubbar = Column(String(100), nullable=True)

    dtcriacao = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
    )
