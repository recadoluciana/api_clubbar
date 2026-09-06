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
