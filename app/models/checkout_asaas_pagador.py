from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, text

from app.database import Base


class CheckoutAsaasPagador(Base):
    __tablename__ = "checkout_asaas_pagador"

    checkout_asaas_pagador_id = Column(BigInteger, primary_key=True, autoincrement=True)
    checkout_asaas_id = Column(
        BigInteger,
        ForeignKey("checkout_asaas.checkout_asaas_id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    venda_id = Column(BigInteger, ForeignKey("venda.venda_id"), nullable=True)
    payment_id = Column(String(100), nullable=True)
    asaas_customer_id = Column(String(100), nullable=True)
    nome = Column(String(150), nullable=True)
    cpf_cnpj = Column(String(20), nullable=True)
    email = Column(String(160), nullable=True)
    telefone = Column(String(20), nullable=True)
    endereco = Column(String(150), nullable=True)
    numero = Column(String(20), nullable=True)
    complemento = Column(String(80), nullable=True)
    bairro = Column(String(80), nullable=True)
    cep = Column(String(10), nullable=True)
    cidade = Column(String(100), nullable=True)
    uf = Column(String(2), nullable=True)
    dtcriacao = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    dtultatu = Column(DateTime, nullable=True, server_onupdate=text("CURRENT_TIMESTAMP"))
