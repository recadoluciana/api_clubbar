from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class EventoLoteOut(BaseModel):
    lote_id: int
    organizacao_id: int
    loja_id: int
    evento_id: int
    produto_id: int

    nmlote: str
    vrprecolote: float

    qttotallote: int
    qtvendidalote: int

    dtiniciovenda: Optional[datetime] = None
    dtfimvenda: Optional[datetime] = None

    statuslote: str

    dtcriacao: datetime
    dtultatu: Optional[datetime] = None

    class Config:
        from_attributes = True  # pydantic v2