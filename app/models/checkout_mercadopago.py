from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String, Text, text

from app.database import Base


class CheckoutMercadoPago(Base):
    """Tentativa de checkout Mercado Pago, isolada do histórico Asaas."""

    __tablename__ = "checkout_mercadopago"

    checkout_mercadopago_id = Column(BigInteger, primary_key=True, autoincrement=True)
    carrinho_id = Column(BigInteger, nullable=True, index=True)
    reserva_ingresso_id = Column(
        BigInteger,
        ForeignKey("reserva_ingresso.reserva_ingresso_id"),
        nullable=True,
        index=True,
    )
    cliente_id = Column(BigInteger, nullable=False, index=True)
    loja_id = Column(BigInteger, nullable=False, index=True)
    venda_id = Column(BigInteger, ForeignKey("venda.venda_id"), nullable=True)

    preference_id = Column(String(120), unique=True, nullable=False)
    payment_id = Column(String(120), unique=True, nullable=True)
    external_reference = Column(String(140), unique=True, nullable=False)
    status = Column(String(30), server_default=text("'PENDING'"))
    checkout_url = Column(String(1000), nullable=True)
    metodo_solicitado = Column(String(30), nullable=True)

    valor = Column(Numeric(10, 2), nullable=False)
    vrtaxaclubbar = Column(Numeric(10, 2), nullable=False, server_default="0")
    dadosentrega = Column(Text, nullable=True)
    dsorigemconfirmacao = Column(String(20), nullable=True)
    dtconfirmacao = Column(DateTime, nullable=True)
    dtcriacao = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"))
