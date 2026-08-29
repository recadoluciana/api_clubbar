#portalparceiro.py
from typing import Literal

from pydantic import BaseModel, Field


class PortalMensagemCreate(BaseModel):
    mensagem: str = Field(min_length=1, max_length=3000)


class PortalAgendamentoResposta(BaseModel):
    status: Literal["CONFIRMADO", "RECUSADO"]


class PortalDecisaoUpdate(BaseModel):
    leadestabelecimento_id: int | None = Field(default=None, gt=0)
    decisao: Literal["ANALISANDO", "ACEITOU", "RECUSOU"]


class PortalEstabelecimentoCreate(BaseModel):
    nmestabelecimento: str = Field(min_length=2, max_length=160)
    tipo: Literal["BAR", "CASA_NOTURNA", "PRODUTOR_EVENTOS", "CASA_EVENTOS"]
    tipovenda: Literal["PRODUTOS", "INGRESSOS", "AMBOS"] = "AMBOS"
    cpfcnpj: str | None = Field(default=None, max_length=18)
    estado_id: int = Field(gt=0)
    cidade_id: int = Field(gt=0)
    mensagem: str | None = Field(default=None, max_length=1000)
