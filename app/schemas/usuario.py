from typing import Optional, Literal

from pydantic import BaseModel, EmailStr, Field


CargoUsuario = Literal[
    "SUPERADMIN",
    "ADMIN",
    "GERENTE",
    "CAIXA",
    "BARMAN",
    "GARCOM",
    "PORTEIRO",
]


class UsuarioBase(BaseModel):
    loja_id: Optional[int] = None

    nmusuario: str = Field(
        ...,
        min_length=3,
        max_length=200,
    )

    emailuser: EmailStr

    dscargo: CargoUsuario = "BARMAN"

    situsuario: str = "ATIVO"


class UsuarioCreate(UsuarioBase):
    senha: str = Field(
        ...,
        min_length=6,
        max_length=100,
    )


class UsuarioUpdate(BaseModel):
    loja_id: Optional[int] = None

    nmusuario: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=200,
    )

    emailuser: Optional[EmailStr] = None

    senha: Optional[str] = Field(
        default=None,
        min_length=6,
        max_length=100,
    )

    dscargo: Optional[CargoUsuario] = None

    situsuario: Optional[str] = None


class UsuarioOut(BaseModel):
    usuario_id: int
    organizacao_id: int
    loja_id: Optional[int] = None

    nmusuario: str
    emailuser: EmailStr

    dscargo: CargoUsuario
    situsuario: str

    class Config:
        from_attributes = True