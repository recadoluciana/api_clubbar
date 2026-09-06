from pydantic import BaseModel, Field, field_validator


class EstiloMusicalIn(BaseModel):
    nmestilomusical: str = Field(min_length=1, max_length=120)
    sitestilomusical: str = "ATIVO"

    @field_validator("nmestilomusical")
    @classmethod
    def validar_nome(cls, valor: str) -> str:
        nome = " ".join(valor.split())
        if not nome:
            raise ValueError("Informe o nome do estilo musical.")
        return nome

    @field_validator("sitestilomusical")
    @classmethod
    def validar_situacao(cls, valor: str) -> str:
        situacao = valor.strip().upper()
        if situacao not in {"ATIVO", "INATIVO"}:
            raise ValueError("A situação deve ser ATIVO ou INATIVO.")
        return situacao


class EstilosMusicaisImportacaoIn(BaseModel):
    estilos_ids: list[int] = Field(min_length=1)
