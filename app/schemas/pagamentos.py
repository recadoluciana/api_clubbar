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


class PagarNovoIn(BaseModel):
    cliente_id: int
    usuario_id: Optional[int] = None
    organizacao_id: int
    loja_id: int

    # PIX ou Cartão
    dsmetodopag: Literal[
        "PIX",
        "CREDIT_CARD",
        "DEBIT_CARD",
        "CREDITO",
        "DEBITO",
    ] = "PIX"

    # Mercado Pago Cartão
    card_token: Optional[str] = None
    payment_method_id: Optional[str] = None
    issuer_id: Optional[str] = None
    installments: Optional[int] = 1

    # Mantidos por compatibilidade
    encrypted_card: Optional[EncryptedStr] = None
    security_code: Optional[CVVStr] = None

    device_id: Optional[str] = None

    # Taxa de ingresso
    percentual_taxa_ingresso: Optional[float] = 0
    percentual_taxa_produto : Optional[float] = 0

    # Idempotência
    idempotency_key: Optional[str] = None

    # Define para qual aplicativo o Checkout Asaas deve retornar.
    origem_checkout: Literal["CLIENT", "PARTNER"] = "CLIENT"
    usar_cashback: bool = False
    valor_cashback: Optional[float] = Field(default=None, ge=0)
    entrega: Optional[dict] = None

class PagarNovoOut(BaseModel):
    venda_id: int
    pagbank_order_id: Optional[str] = None
    status: str


class CriarPedidoEntregaIn(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int
    cep: str = Field(min_length=8, max_length=10)
    endereco: str = Field(min_length=2, max_length=255)
    numero: str = Field(min_length=1, max_length=20)
    complemento: str | None = Field(default=None, max_length=120)
    bairro: str = Field(min_length=2, max_length=120)
    cidade: str = Field(min_length=2, max_length=120)
    uf: str = Field(min_length=2, max_length=2)
    observacao: str | None = Field(default=None, max_length=255)

class PagarPixRequest(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int
