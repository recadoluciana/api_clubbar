from pydantic import BaseModel, EmailStr
from typing import Optional


class UsuarioBase(BaseModel):
    loja_id: Optional[int] = None
    nmusuario: str
    emailuser: EmailStr
    dscargo: Optional[str] = "FUNCIONARIO"
    situsuario: Optional[str] = "ATIVO"


class UsuarioCreate(UsuarioBase):
    senha: str


class UsuarioUpdate(BaseModel):
    loja_id: Optional[int] = None
    nmusuario: Optional[str] = None
    emailuser: Optional[EmailStr] = None
    senha: Optional[str] = None
    dscargo: Optional[str] = None
    situsuario: Optional[str] = None


class UsuarioOut(BaseModel):
    usuario_id: int
    organizacao_id: int
    loja_id: Optional[int] = None
    nmusuario: str
    emailuser: EmailStr
    dscargo: str
    situsuario: str

    class Config:
        from_attributes = True