# app/models/pagvenda.py
from sqlalchemy import (
    BigInteger, Column, DateTime, Enum, ForeignKey, Numeric, String
)
from sqlalchemy.sql import func

from app.database import Base


class PagVenda(Base):
    __tablename__ = "pagvenda"

    pagvenda_id = Column(BigInteger, primary_key=True, autoincrement=True)

    venda_id = Column(BigInteger, ForeignKey("venda.venda_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False)

    dsmetodopag = Column(
        String(40),
        nullable=False,
    )
    
    vrpagvenda = Column(Numeric(10, 2), nullable=False)

    sitpagvenda = Column(Enum("PENDENTE", "PAGO", "CANCELADO", name="sitpagvenda_enum"), nullable=False, server_default="PENDENTE")

    idtransacaopagvenda = Column(String(120), nullable=True)
    dtconftranspagvenda = Column(DateTime, nullable=True)

    # ✅ Campos para PagBank (recomendados)
    provedor = Column(
        String(30),
        nullable=False,
        server_default="MERCADOPAGO",
    )
    reference_id = Column(String(80), nullable=True)
    checkout_id = Column(String(120), nullable=True)
    pay_url = Column(String(255), nullable=True)

    dtcriacao = Column(DateTime, nullable=False, server_default=func.current_timestamp())
