from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, model_validator

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

class EventoRapidoAgendaIn(BaseModel):
    loja_id: int
    nmtituloevento: str = Field(min_length=1, max_length=120)
    atracao_id: int
    dtinicioatracao: datetime
    dtfimatracao: datetime
    preco_lote: Decimal = Field(ge=0, decimal_places=2)

    @model_validator(mode="after")
    def validar_periodo(self):
        self.nmtituloevento = self.nmtituloevento.strip()
        if not self.nmtituloevento:
            raise ValueError("Informe o nome do evento.")
        if self.dtfimatracao <= self.dtinicioatracao:
            raise ValueError("O fim da atração deve ser posterior ao início.")
        return self
