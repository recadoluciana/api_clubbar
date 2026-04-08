from pydantic import BaseModel, Field
from typing import Optional


class ClientePerfilUpdate(BaseModel):
    nmcliente: str = Field(min_length=3, max_length=120)
    nrtelcliente: Optional[str] = Field(default=None, max_length=15)
    nrcpfcliente: Optional[str] = Field(default=None, max_length=15)

class AlterarSenhaClienteRequest(BaseModel):
    senha_atual: str = Field(min_length=1)
    nova_senha: str = Field(min_length=6, max_length=100)