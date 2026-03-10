# app/schemas/evento.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class EventoOutBR(BaseModel):
    evento_id: int
    organizacao_id: int
    loja_id: int

    nmtituloevento: str
    dsdescevento: Optional[str] = None

    dtinicioevento: datetime
    dtfimevento: datetime | None = None

    nmlocalevento: Optional[str] = None
    dsendlocevento: Optional[str] = None
    urlbannerevento: Optional[str] = None

    statusevento: str

    nmloja: Optional[str] = None
    nmcidade: Optional[str] = None

class ListaEventoIn(BaseModel):
    cidade_id: int