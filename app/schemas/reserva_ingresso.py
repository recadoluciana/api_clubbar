from pydantic import BaseModel, Field, field_validator


class ReservaIngressoCreate(BaseModel):
    cliente_id: int
    lote_id: int
    quantidade: int = Field(ge=1, le=20)


class ParticipanteReservaIn(BaseModel):
    nome: str = Field(min_length=3, max_length=150)
    cpf: str

    @field_validator("cpf")
    @classmethod
    def normalizar_cpf(cls, value: str) -> str:
        cpf = "".join(char for char in value if char.isdigit())
        if len(cpf) != 11:
            raise ValueError("CPF deve possuir 11 dígitos")
        return cpf


class ParticipantesReservaUpdate(BaseModel):
    participantes: list[ParticipanteReservaIn]


class PagamentoReservaIn(BaseModel):
    cliente_id: int
    parcelas: int = Field(default=1, ge=1, le=12)

