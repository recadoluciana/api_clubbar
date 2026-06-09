# app/schemas/pagamentos.py
from pydantic import BaseModel, Field, constr
from typing import Literal, Optional


class CheckoutCreateIn(BaseModel):
    organizacao_id: int
    loja_id: int
    cliente_id: int
    plataforma: Literal["ANDROID", "IOS", "TOTEM", "OUTROS"] = "OUTROS"


class CheckoutCreateOut(BaseModel):
    venda_id: int
    pagvenda_id: int
    pay_url: str


class VendaStatusOut(BaseModel):
    venda_id: int
    sitvenda: Literal["PENDENTE", "PAGA", "CANCELADA"]
    sitpagvenda: Optional[Literal["PENDENTE", "PAGO", "CANCELADO"]] = None
    totalvenda: float

# 🔐 Tipos validados
EncryptedStr = constr(min_length=20)
CVVStr       = constr(pattern=r"^\d{3,4}$")

from typing import Optional, Literal
from pydantic import BaseModel


class PagarNovoIn(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int

    # PIX ou Cartão
    dsmetodopag: Literal[
        "PIX",
        "CREDIT_CARD",
        "DEBIT_CARD",
    ] = "PIX"

    # Mercado Pago Cartão
    card_token: Optional[str] = None
    payment_method_id: Optional[str] = None
    issuer_id: Optional[str] = None
    installments: Optional[int] = 1

    # Mantidos por compatibilidade
    encrypted_card: Optional[EncryptedStr] = None
    security_code: Optional[CVVStr] = None

    # Idempotência
    idempotency_key: Optional[str] = None

class PagarNovoOut(BaseModel):
    venda_id: int
    pagbank_order_id: Optional[str] = None
    status: str

class PagarPixRequest(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int