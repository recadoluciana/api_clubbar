from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    field_validator,
)


TipoParceiro = Literal[
    "BAR",
    "CASA_NOTURNA",
    "EVENTO",
]


StatusLeadParceiroSchema = Literal[
    "NOVO",
    "CONTATADO",
    "NEGOCIANDO",
    "CONVERTIDO",
    "PERDIDO",
]


class ConverterLeadParceiroIn(BaseModel):
    razao_social: str = Field(
        min_length=3,
        max_length=160,
    )

    cnpj: str = Field(
        min_length=14,
        max_length=18,
    )

    cep: str | None = Field(
        default=None,
        max_length=20,
    )

    endereco: str = Field(
        min_length=3,
        max_length=255,
    )

    numero: str = Field(
        min_length=1,
        max_length=20,
    )

    complemento: str | None = Field(
        default=None,
        max_length=120,
    )

    bairro: str | None = Field(
        default=None,
        max_length=120,
    )
    
class LeadParceiroCreate(BaseModel):
    nmresponsavel: str = Field(
        ...,
        min_length=3,
        max_length=120,
    )

    nmestabelecimento: str = Field(
        ...,
        min_length=2,
        max_length=160,
    )

    tipo: TipoParceiro

    telefone: str = Field(
        ...,
        min_length=10,
        max_length=30,
    )

    email: EmailStr

    estado_id: int = Field(
        ...,
        gt=0,
    )

    cidade_id: int = Field(
        ...,
        gt=0,
    )

    mensagem: str | None = Field(
        default=None,
        max_length=1000,
    )

    @field_validator(
        "nmresponsavel",
        "nmestabelecimento",
    )
    @classmethod
    def validar_textos_obrigatorios(
        cls,
        valor: str,
    ) -> str:
        texto = valor.strip()

        if not texto:
            raise ValueError(
                "O campo não pode ficar vazio."
            )

        return texto

    @field_validator("telefone")
    @classmethod
    def validar_telefone(
        cls,
        valor: str,
    ) -> str:
        numeros = "".join(
            caractere
            for caractere in valor
            if caractere.isdigit()
        )

        if len(numeros) not in (10, 11):
            raise ValueError(
                "Informe um telefone válido com DDD."
            )

        return numeros

    @field_validator("email")
    @classmethod
    def normalizar_email(
        cls,
        valor: EmailStr,
    ) -> str:
        return str(valor).strip().lower()

    @field_validator("mensagem")
    @classmethod
    def normalizar_mensagem(
        cls,
        valor: str | None,
    ) -> str | None:
        if valor is None:
            return None

        texto = valor.strip()

        return texto or None


class LeadParceiroUpdate(BaseModel):
    nmresponsavel: str | None = Field(
        default=None,
        min_length=3,
        max_length=120,
    )

    tipo: TipoParceiro | None = None

    telefone: str | None = Field(
        default=None,
        min_length=10,
        max_length=30,
    )

    email: EmailStr | None = None

    status: StatusLeadParceiroSchema | None = None

    @field_validator("nmresponsavel")
    @classmethod
    def normalizar_responsavel(
        cls,
        valor: str | None,
    ) -> str | None:
        if valor is None:
            return None

        texto = valor.strip()

        if not texto:
            raise ValueError(
                "Informe o nome do responsável."
            )

        return texto

    @field_validator("telefone")
    @classmethod
    def validar_telefone_update(
        cls,
        valor: str | None,
    ) -> str | None:
        if valor is None:
            return None

        numeros = "".join(
            caractere
            for caractere in valor
            if caractere.isdigit()
        )

        if len(numeros) not in (10, 11):
            raise ValueError(
                "Informe um telefone válido com DDD."
            )

        return numeros

    @field_validator("email")
    @classmethod
    def normalizar_email_update(
        cls,
        valor: EmailStr | None,
    ) -> str | None:
        if valor is None:
            return None

        return str(valor).strip().lower()


class LeadParceiroOut(BaseModel):
    leadparceiro_id: int

    nmresponsavel: str
    nmestabelecimento: str

    tipo: TipoParceiro

    telefone: str
    email: str

    estado_id: int
    cidade_id: int

    nmestado: str
    sgestado: str
    nmcidade: str

    mensagem: str | None = None

    status: StatusLeadParceiroSchema

    dtcriacao: datetime
    dtultatu: datetime | None = None

    dias_espera: int

    class Config:
        from_attributes = True

