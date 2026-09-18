# app/schemas/auth.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

class ClienteRegister(BaseModel):
    nmcliente   : str = Field(min_length=3, max_length=120)
    emailcliente: EmailStr
    senhahashcli: str = Field(min_length=6, max_length=72)
    nrtelcliente: Optional[str] = None
    nrcpfcliente: str = Field(min_length=11, max_length=15)
    endcliente: str = Field(min_length=2, max_length=150)
    nrendcliente: str = Field(min_length=1, max_length=20)
    complcliente: Optional[str] = Field(default=None, max_length=80)
    bairrocliente: str = Field(min_length=2, max_length=80)
    cepcliente: str = Field(min_length=8, max_length=10)
    cidadecliente: str = Field(min_length=2, max_length=100)
    ufcliente: str = Field(min_length=2, max_length=2)

class ClienteLogin(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=6, max_length=72)

class UserLogin(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=4, max_length=72)

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ClientePublic(BaseModel):
    cliente_id: int
    nmcliente: str
    emailcliente: EmailStr
    emailconf: str  # "S" / "N"
class EsqueciSenhaUsuarioRequest(BaseModel):
    email: EmailStr

class RedefinirSenhaUsuarioRequest(BaseModel):
    email: EmailStr
    codigo: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
    nova_senha: str = Field(min_length=6, max_length=72)
