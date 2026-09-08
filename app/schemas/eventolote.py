from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, model_validator

class EventoLotePrecoIn(BaseModel):
    nmpreco: str = Field(min_length=1, max_length=100)
    tipopreco: Literal["INTEIRA", "MEIA_LEGAL", "MEIA_IDOSO", "SOCIAL", "CORTESIA", "OUTRO"]
    vrpreco: float = Field(ge=0)
    aplicacotalegal: bool = False
    exigecomprovante: bool = False
    situacao: Literal["ATIVO", "INATIVO"] = "ATIVO"
    nrordem: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def normalizar_regra(self):
        if self.tipopreco == "MEIA_LEGAL": self.aplicacotalegal, self.exigecomprovante = True, True
        elif self.tipopreco == "MEIA_IDOSO": self.aplicacotalegal, self.exigecomprovante = False, True
        return self

class EventoLoteCreate(BaseModel):
    organizacao_id: int
    loja_id: int
    nmlote: str = Field(..., min_length=1, max_length=80)
    eventosetor_id: int
    nrlote: int = Field(default=1, ge=1)
    qttotallote: int | None = Field(default=None, gt=0)
    usarcapacidaderestante: bool = False
    dtiniciovenda: datetime | None = None
    dtfimvenda: datetime | None = None
    statuslote: Literal["ATIVO", "ESGOTADO", "ENCERRADO", "INATIVO"] = "ATIVO"
    precos: list[EventoLotePrecoIn] = Field(min_length=1)

    @model_validator(mode="after")
    def validar_quantidade(self):
        if not self.usarcapacidaderestante and self.qttotallote is None:
            raise ValueError("Informe o limite comercial do lote")
        if self.usarcapacidaderestante:
            self.qttotallote = None
        return self

class EventoLoteUpdate(BaseModel):
    nmlote: str | None = Field(None, min_length=1, max_length=80)
    eventosetor_id: int | None = None
    nrlote: int | None = Field(None, ge=1)
    qttotallote: int | None = Field(None, gt=0)
    usarcapacidaderestante: bool | None = None
    dtiniciovenda: datetime | None = None
    dtfimvenda: datetime | None = None
    statuslote: Literal["ATIVO", "ESGOTADO", "ENCERRADO", "INATIVO"] | None = None
    precos: list[EventoLotePrecoIn] | None = None

class EventoLotePrecoOut(EventoLotePrecoIn):
    lotepreco_id: int
    class Config: from_attributes = True

class EventoLoteOut(BaseModel):
    lote_id: int
    organizacao_id: int
    loja_id: int
    evento_id: int
    nmlote: str
    eventosetor_id: int
    nmsetor: str | None = None
    nrlote: int
    qttotallote: int | None
    usarcapacidaderestante: bool = False
    qtvendidalote: int | None = 0
    dtiniciovenda: datetime | None = None
    dtfimvenda: datetime | None = None
    statuslote: str
    precos: list[EventoLotePrecoOut]
    cotalegal: int = 0
    qtvendidacotalegal: int = 0
    class Config: from_attributes = True
