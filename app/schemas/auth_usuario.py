from pydantic import BaseModel, EmailStr, Field

class LoginUsuarioIn(BaseModel):
    organizacao_id: int = Field(..., ge=1)
    emailuser: EmailStr
    senha: str = Field(..., min_length=4)

class LoginUsuarioOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

    # Dados do usuário (nomes iguais ao banco)
    usuario_id: int
    organizacao_id: int
    loja_id: int | None = None
    nmusuario: str
    emailuser: str
    dscargo: str
    situsuario: str
