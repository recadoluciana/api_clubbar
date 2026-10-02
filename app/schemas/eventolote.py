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
    def normalizar_regras_da_modalidade(self):
        if self.tipopreco == "INTEIRA":
            self.aplicacotalegal = False
            self.exigecomprovante = False
        return self


class EventoLoteSetorIn(BaseModel):
    eventosetor_id: int
    qtlimite: int | None = Field(default=None, gt=0)
    precos: list[EventoLotePrecoIn] = Field(min_length=1)

    @model_validator(mode="after")
    def modalidades_nao_repetidas(self):
        tipos = [preco.tipopreco for preco in self.precos]
        if len(tipos) != len(set(tipos)):
            raise ValueError("Não repita uma modalidade de preço no mesmo setor")
        return self


class EventoLoteGlobalCreate(BaseModel):
    organizacao_id: int
    loja_id: int
    nrlote: int | None = Field(default=None, ge=1)
    nmlote: str | None = Field(default=None, min_length=1, max_length=80)
    dtiniciovenda: datetime | None = None
    dtfimvenda: datetime | None = None
    gatilhovirada: Literal["DATA", "ESGOTAMENTO", "HIBRIDO"] = "HIBRIDO"
    setores: list[EventoLoteSetorIn] = Field(min_length=1)

    @model_validator(mode="after")
    def periodo_valido(self):
        if self.dtiniciovenda and self.dtfimvenda and self.dtfimvenda <= self.dtiniciovenda:
            raise ValueError("O fim das vendas deve ser posterior ao início")
        return self


class EventoLoteGlobalUpdate(BaseModel):
    nmlote: str | None = Field(default=None, min_length=1, max_length=80)
    dtiniciovenda: datetime | None = None
    dtfimvenda: datetime | None = None
    gatilhovirada: Literal["DATA", "ESGOTAMENTO", "HIBRIDO"] | None = None
    situacao: Literal["ATIVO", "INATIVO"] | None = None

    @model_validator(mode="after")
    def periodo_valido(self):
        if self.dtiniciovenda and self.dtfimvenda and self.dtfimvenda <= self.dtiniciovenda:
            raise ValueError("O fim das vendas deve ser posterior ao início")
        return self


class EventoLoteSetorUpdate(BaseModel):
    qtlimite: int | None = Field(default=None, gt=0)
    situacao: Literal["ATIVO", "INATIVO"] | None = None
    precos: list[EventoLotePrecoIn] | None = None


# Nomes antigos mantidos como aliases de importação durante a transição dos
# aplicativos Flutter. Não representam mais um lote independente por setor.
EventoLoteCreate = EventoLoteGlobalCreate
EventoLoteUpdate = EventoLoteSetorUpdate


class EventoLotePrecoOut(EventoLotePrecoIn):
    lotepreco_id: int

    class Config:
        from_attributes = True


class EventoLoteOut(BaseModel):
    lote_id: int
    loteglobal_id: int
    organizacao_id: int
    loja_id: int
    evento_id: int
    nmlote: str
    eventosetor_id: int
    nmsetor: str | None = None
    nrlote: int
    qttotallote: int | None = None
    qtvendidalote: int = 0
    dtiniciovenda: datetime | None = None
    dtfimvenda: datetime | None = None
    gatilhovirada: str
    statuslote: str
    precos: list[EventoLotePrecoOut]
    cotalegal: int = 0
    qtvendidacotalegal: int = 0
    qtreservadacotalegal: int = 0

    class Config:
        from_attributes = True
