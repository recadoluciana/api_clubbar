from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr


class LeadParceiroCreate(BaseModel):
    nome_responsavel: str
    nome_estabelecimento: str
    tipo: str
    telefone: str
    email: EmailStr
    cidade: str
    mensagem: Optional[str] = None


class LeadParceiroOut(BaseModel):
    lead_parceiro_id: int

    nome_responsavel: str
    nome_estabelecimento: str
    tipo: str

    telefone: str
    email: str
    cidade: str

    mensagem: Optional[str]

    status: str

    dtcriacao: datetime
    dtultatu: Optional[datetime]

    class Config:
        from_attributes = True