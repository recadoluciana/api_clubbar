from typing import Literal

from pydantic import BaseModel


class ProvedorPagamentoIn(BaseModel):
    provedor_pagamento: Literal["ASAAS", "MERCADO_PAGO"]


class LojaMercadoPagoOut(BaseModel):
    loja_id: int
    organizacao_id: int
    ambiente: str
    mercadopago_user_id: str | None = None
    statusintegracao: str
    conectada: bool
    provedor_pagamento: str


class MercadoPagoAutorizacaoOut(BaseModel):
    authorization_url: str
