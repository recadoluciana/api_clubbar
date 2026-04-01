from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


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

    statuslote: Literal["ATIVO", "ESGOTADO", "ENCERRADO", "INATIVO"]

    dtcriacao: datetime
    dtultatu: Optional[datetime] = None

    class Config:
        from_attributes = True


class EventoLoteCreate(BaseModel):
    organizacao_id: int
    loja_id: int
    nmlote: str = Field(..., min_length=1, max_length=80)
    vrprecolote: float
    qttotallote: int
    qtvendidalote: Optional[int] = 0
    dtiniciovenda: Optional[datetime] = None
    dtfimvenda: Optional[datetime] = None
    statuslote: Optional[Literal["ATIVO", "ESGOTADO", "ENCERRADO", "INATIVO"]] = "ATIVO"


class EventoLoteUpdate(BaseModel):
    organizacao_id: Optional[int] = None
    loja_id: Optional[int] = None
    evento_id: Optional[int] = None
    nmlote: Optional[str] = Field(None, min_length=1, max_length=80)
    vrprecolote: Optional[float] = None
    qttotallote: Optional[int] = None
    qtvendidalote: Optional[int] = None
    dtiniciovenda: Optional[datetime] = None
    dtfimvenda: Optional[datetime] = None
    statuslote: Optional[Literal["ATIVO", "ESGOTADO", "ENCERRADO", "INATIVO"]] = None