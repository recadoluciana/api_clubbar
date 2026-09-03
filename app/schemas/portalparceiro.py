#portalparceiro.py
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class PortalMensagemCreate(BaseModel):
    mensagem: str = Field(min_length=1, max_length=3000)


class PortalLoginLead(BaseModel):
    email: EmailStr
    telefone: str = Field(min_length=10, max_length=30)


class PortalRecuperarDados(BaseModel):
    email: EmailStr


class PortalAgendamentoResposta(BaseModel):
    status: Literal["CONFIRMADO", "RECUSADO"]


class PortalStatusUpdate(BaseModel):
    leadestabelecimento_id: int | None = Field(default=None, gt=0)
    status: Literal["NEGOCIANDO", "ACEITOU_PARCERIA", "RECUSOU_PARCERIA"]


class PortalEstabelecimentoCreate(BaseModel):
    nmestabelecimento: str = Field(min_length=2, max_length=160)
    nmresponsavel: str | None = Field(default=None, max_length=120)
    telefone_responsavel: str | None = Field(default=None, max_length=30)
    email_responsavel: EmailStr | None = None
    tipo: Literal["BAR", "CASA_NOTURNA", "PRODUTOR_EVENTOS", "CASA_EVENTOS"]
    tipovenda: Literal["PRODUTOS", "INGRESSOS", "AMBOS"] = "AMBOS"
    cpfcnpj: str | None = Field(default=None, max_length=18)
    telefone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    estado_id: int = Field(gt=0)
    cidade_id: int = Field(gt=0)
    cep: str | None = Field(default=None, max_length=9)
    endereco: str | None = Field(default=None, max_length=255)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=120)
    bairro: str | None = Field(default=None, max_length=120)
    mensagem: str | None = Field(default=None, max_length=1000)
