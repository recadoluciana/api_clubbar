#checkout_asaas.py
from sqlalchemy import BigInteger, Column, DateTime, String, text

from app.database import Base


class CheckoutAsaas(Base):
    __tablename__ = "checkout_asaas"

    checkout_asaas_id = Column(BigInteger, primary_key=True, autoincrement=True)

    carrinho_id = Column(BigInteger, nullable=False)
    cliente_id = Column(BigInteger, nullable=False)
    loja_id = Column(BigInteger, nullable=False)

    checkout_id = Column(String(100), unique=True, nullable=False)
    payment_id = Column(String(100))

    external_reference = Column(String(100))
    status = Column(String(30), server_default=text("'ACTIVE'"))

    dtcriacao = Column(
        DateTime,
        server_default=text("CURRENT_TIMESTAMP"),
    )