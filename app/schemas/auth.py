# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field

class ClienteRegister(BaseModel):
    nome: str = Field(min_length=2, max_length=120)
    email: EmailStr
    senha: str = Field(min_length=6, max_length=72)

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
