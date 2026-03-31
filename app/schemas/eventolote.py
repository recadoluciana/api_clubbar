from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class EventoLoteOut(BaseModel):
    lote_id: int
    organizacao_id: int
    loja_id: int
    evento_id: int
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

class EventoLoteCreate(BaseModel):
    organizacao_id: int
    loja_id: int
    evento_id: int
    nmlote: str
    vrprecolote: float
    qttotallote: int
    qtvendidalote: Optional[int] = 0
    dtiniciovenda: Optional[datetime] = None
    dtfimvenda: Optional[datetime] = None
    statuslote: Optional[str] = "ATIVO"


class EventoLoteUpdate(BaseModel):
    organizacao_id: Optional[int] = None
    loja_id: Optional[int] = None
    evento_id: Optional[int] = None
    nmlote: Optional[str] = None
    vrprecolote: Optional[float] = None
    qttotallote: Optional[int] = None
    qtvendidalote: Optional[int] = None
    dtiniciovenda: Optional[datetime] = None
    dtfimvenda: Optional[datetime] = None
    statuslote: Optional[str] = None