# app/schemas/pagamentos.py
from pydantic import BaseModel, Field
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
