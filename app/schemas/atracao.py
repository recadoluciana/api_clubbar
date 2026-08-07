from datetime import datetime
from pydantic import BaseModel, model_validator

class EventoAtracaoIn(BaseModel):
    atracao_id: int
    dtinicioatracao: datetime
    dtfimatracao: datetime
    @model_validator(mode="after")
    def validar_periodo(self):
        if self.dtfimatracao <= self.dtinicioatracao:
            raise ValueError("O fim da atração deve ser posterior ao início.")
        return self

class EventoAtracaoUpdate(BaseModel):
    atracao_id: int | None = None
    dtinicioatracao: datetime | None = None
    dtfimatracao: datetime | None = None
