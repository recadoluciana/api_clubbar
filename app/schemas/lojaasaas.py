from pydantic import BaseModel, Field


class LojaAsaasConfigIn(BaseModel):
    asaas_account_id: str | None = Field(default=None, max_length=100)
    asaas_wallet_id: str = Field(min_length=1, max_length=100)
    asaas_api_key: str = Field(min_length=20)
    webhook_token: str = Field(min_length=32, max_length=255)
    statusintegracao: str = Field(default="ATIVA", pattern="^(ATIVA|INATIVA)$")


class LojaAsaasConfigOut(BaseModel):
    loja_id: int
    organizacao_id: int
    ambiente: str
    asaas_account_id: str | None
    asaas_wallet_id: str
    statusintegracao: str
    configurada: bool = True
