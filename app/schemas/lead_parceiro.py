#lead_parceiro.py
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class LeadParceiroCreate(BaseModel):
    nome_responsavel: str = Field(..., min_length=2, max_length=120)
    nome_estabelecimento: str = Field(..., min_length=2, max_length=160)
    tipo: str = Field(..., min_length=2, max_length=30)

    telefone: str = Field(..., min_length=8, max_length=30)
    email: EmailStr
    cidade: str = Field(..., min_length=2, max_length=120)

    mensagem: Optional[str] = Field(None, max_length=2000)


class LeadParceiroOut(BaseModel):
    lead_parceiro_id: int
    nome_responsavel: str
    nome_estabelecimento: str
    tipo: str
    telefone: str
    email: str
    cidade: str
    mensagem: Optional[str] = None
    status: str

    class Config:
        from_attributes = True