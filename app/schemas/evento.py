# app/schemas/evento.py
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class EventoOutBR(BaseModel):
    evento_id: int
    organizacao_id: int
    loja_id: int
    produto_id_ingresso: int

    nmtituloevento: str
    dsdescevento: Optional[str] = None

    dtinicioevento: str
    dtfimvevento: str

    nmlocalevento: Optional[str] = None
    dsendlocevento: Optional[str] = None
    urlbannerevento: Optional[str] = None

    statusevento: str

class ListaEventoIn(BaseModel):
    cidade_id: int