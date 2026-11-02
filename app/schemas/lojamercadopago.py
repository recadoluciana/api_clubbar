from typing import Literal

from pydantic import BaseModel


class ProvedorPagamentoIn(BaseModel):
    provedor_pagamento: Literal["ASAAS", "MERCADO_PAGO"]


class LojaMercadoPagoOut(BaseModel):
    loja_id: int
    organizacao_id: int
    ambiente: str
    mercadopago_user_id: str | None = None
    mercadopago_nome: str | None = None
    mercadopago_titular: str | None = None
    mercadopago_email: str | None = None
    statusintegracao: str
    conectada: bool
    conta_pendente: dict[str, str] | None = None
    provedor_pagamento: str


class MercadoPagoAutorizacaoOut(BaseModel):
    authorization_url: str


class MercadoPagoConfirmacaoIn(BaseModel):
    confirmacao_id: str
    confirmar: bool
