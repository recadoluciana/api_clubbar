from datetime import datetime
from pydantic import BaseModel, Field, model_validator

class AgendarEventoModeloIn(BaseModel):
    dtinicio: datetime
    dtfim: datetime | None = None
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
        return self


class EventoModeloAtracaoIn(BaseModel):
    atracao_id: int
    ordem: int = Field(ge=1, le=100)
    nrminutoinicio: int = Field(ge=0, le=10080)
    nrminutoduracao: int = Field(gt=0, le=1440)


class EventoModeloAtracaoUpdate(BaseModel):
    atracao_id: int | None = None
    ordem: int | None = Field(default=None, ge=1, le=100)
    nrminutoinicio: int | None = Field(default=None, ge=0, le=10080)
    nrminutoduracao: int | None = Field(default=None, gt=0, le=1440)
