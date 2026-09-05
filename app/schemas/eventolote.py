from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, Field


class EventoLoteOut(BaseModel):
    lote_id: int
    organizacao_id: int
    loja_id: int
    evento_id: int
    nmlote: str
    eventosetor_id: Optional[int] = None
    nmsetor: Optional[str] = None
    nrlote: int = 1
    tipoingresso: str = "UNICO"
    vrprecolote: float

    qttotallote: Optional[int] = None
    qtvendidalote: Optional[int] = None

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
    eventosetor_id: Optional[int] = None
    nrlote: int = Field(default=1, ge=1)
    tipoingresso: Literal["UNICO", "INTEIRA", "MEIA", "SOCIAL", "CORTESIA", "OUTRO"] = "UNICO"
    vrprecolote: float
    qttotallote: Optional[int] = None
    qtvendidalote: Optional[int] = None
    dtiniciovenda: Optional[datetime] = None
    dtfimvenda: Optional[datetime] = None
    statuslote: Optional[Literal["ATIVO", "ESGOTADO", "ENCERRADO", "INATIVO"]] = "ATIVO"


class EventoLoteUpdate(BaseModel):
    organizacao_id: Optional[int] = None
    loja_id: Optional[int] = None
    evento_id: Optional[int] = None
    nmlote: Optional[str] = Field(None, min_length=1, max_length=80)
    eventosetor_id: Optional[int] = None
    nrlote: Optional[int] = Field(None, ge=1)
    tipoingresso: Optional[Literal["UNICO", "INTEIRA", "MEIA", "SOCIAL", "CORTESIA", "OUTRO"]] = None
    vrprecolote: Optional[float] = None
    qttotallote: Optional[int] = None
    qtvendidalote: Optional[int] = None
    dtiniciovenda: Optional[datetime] = None
    dtfimvenda: Optional[datetime] = None
    statuslote: Optional[Literal["ATIVO", "ESGOTADO", "ENCERRADO", "INATIVO"]] = None
