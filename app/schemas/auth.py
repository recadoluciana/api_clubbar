# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class ClienteRegister(BaseModel):
    nome: str
    email: str
    senha: str
    nrtelcliente: Optional[str] = None
    nrcpfcliente: Optional[str] = None

class ClienteLogin(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=6, max_length=72)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ClientePublic(BaseModel):
    cliente_id: int
    nmcliente: str
    emailcliente: EmailStr
    emailconf: str  # "S" / "N"
