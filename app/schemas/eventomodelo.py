from datetime import datetime
from pydantic import BaseModel, Field, model_validator

class AgendarEventoModeloIn(BaseModel):
    loja_id: int = Field(gt=0)
    dtinicio: datetime
    dtfim: datetime | None = None
    capacidade: int = Field(gt=0)
    nome_setor_inicial: str = Field(default="Pista", min_length=1, max_length=80)
    preco_inteira: float | None = Field(default=None, ge=0)
    local: str | None = Field(default=None, max_length=120)
    endereco: str | None = Field(default=None, max_length=200)
    recorrencia: str = "UNICA"
    repeticoes: int = Field(default=1, ge=1, le=60)

    @model_validator(mode="after")
    def validar(self):
        self.recorrencia = self.recorrencia.strip().upper()
        if self.recorrencia not in {"UNICA", "SEMANAL", "QUINZENAL", "MENSAL"}:
            raise ValueError("Recorrência inválida.")
        if self.recorrencia == "UNICA": self.repeticoes = 1
        if self.dtfim is not None and self.dtfim <= self.dtinicio:
            raise ValueError("O fim deve ser posterior ao início.")
        self.nome_setor_inicial = self.nome_setor_inicial.strip()
        if not self.nome_setor_inicial:
            raise ValueError("Informe o nome do primeiro setor.")
        return self


class EventoModeloAtracaoIn(BaseModel):
    atracao_id: int
    ordem: int = Field(ge=1, le=100)
    nrminutoduracao: int = Field(gt=0, le=1440)


class EventoModeloAtracaoUpdate(BaseModel):
    atracao_id: int | None = None
    ordem: int | None = Field(default=None, ge=1, le=100)
    nrminutoduracao: int | None = Field(default=None, gt=0, le=1440)
