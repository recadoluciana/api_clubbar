from pydantic import BaseModel, Field


class AlterarSenhaClienteRequest(BaseModel):
    senha_atual: str = Field(min_length=1)
    nova_senha: str = Field(min_length=6, max_length=100)