#portalparceiro.py
from typing import Literal

from pydantic import BaseModel, Field


class PortalMensagemCreate(BaseModel):
    mensagem: str = Field(min_length=1, max_length=3000)


class PortalAgendamentoResposta(BaseModel):
    status: Literal["CONFIRMADO", "RECUSADO"]


class PortalDecisaoUpdate(BaseModel):
    decisao: Literal["ACEITOU", "DUVIDAS", "RECUSOU"]