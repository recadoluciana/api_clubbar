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
    "PRODUTOR_EVENTOS",
    "CASA_EVENTOS",
]


TipoVendaLead = Literal[
    "PRODUTOS",
    "INGRESSOS",
    "AMBOS",
]

StatusLeadEstabelecimentoSchema = Literal[
    "NOVO",
    "CONTATADO",
    "NEGOCIANDO",
    "ACEITOU_PARCERIA",
    "CONVERTIDO",
    "RECUSOU_PARCERIA",
]


class ConverterLeadParceiroIn(BaseModel):
    leadestabelecimento_id: int | None = Field(default=None, gt=0)
    nome_organizacao: str = Field(min_length=2, max_length=120)
    nome_loja: str = Field(min_length=2, max_length=120)
    tipo_loja: TipoParceiro
    email_responsavel: EmailStr
    taxa_produtos: float = Field(default=5, ge=0, le=100)
    taxa_ingressos: float = Field(default=5, ge=0, le=100)
    titularfinanceiro_id: int | None = Field(default=None, gt=0)


class LeadEstabelecimentoCreate(BaseModel):
    nmestabelecimento: str = Field(min_length=2, max_length=160)
    tipo: TipoParceiro
    tipovenda: TipoVendaLead = "AMBOS"
    cpfcnpj: str | None = Field(default=None, max_length=18)
    telefone: str | None = Field(default=None, min_length=10, max_length=30)
    email: EmailStr | None = None
    estado_id: int = Field(gt=0)
    cidade_id: int = Field(gt=0)
    cep: str | None = Field(default=None, max_length=9)
    endereco: str | None = Field(default=None, max_length=255)
    numero: str | None = Field(default=None, max_length=20)
    complemento: str | None = Field(default=None, max_length=120)
    bairro: str | None = Field(default=None, max_length=120)
    mensagem: str | None = Field(default=None, max_length=1000)

    @field_validator("cpfcnpj", "telefone", "cep")
    @classmethod
    def somente_numeros_opcional(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        numeros = "".join(caractere for caractere in valor if caractere.isdigit())
        return numeros or None

    @field_validator("email")
    @classmethod
    def normalizar_email_estabelecimento(cls, valor: EmailStr | None) -> str | None:
        return str(valor).strip().lower() if valor is not None else None


class LeadEstabelecimentoUpdate(LeadEstabelecimentoCreate):
    pass


class LeadEstabelecimentoOut(BaseModel):
    leadestabelecimento_id: int
    leadparceiro_id: int
    nmestabelecimento: str
    tipo: TipoParceiro
    tipovenda: TipoVendaLead
    cpfcnpj: str | None = None
    telefone: str | None = None
    email: str | None = None
    estado_id: int
    cidade_id: int
    cep: str | None = None
    endereco: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    mensagem: str | None = None
    status: StatusLeadEstabelecimentoSchema
    vrtaxaprod: float
    vrtaxaing: float
    dtcriacao: datetime
    dtaceite: datetime | None = None
    dtconversao: datetime | None = None

    class Config:
        from_attributes = True

class LeadParceiroCreate(BaseModel):
    nmresponsavel: str = Field(
        ...,
        min_length=3,
        max_length=120,
    )

    nmorganizacao: str | None = Field(default=None, max_length=160)

    telefone: str = Field(
        ...,
        min_length=10,
        max_length=30,
    )

    email: EmailStr

    estabelecimentos: list[LeadEstabelecimentoCreate] = Field(min_length=1, max_length=20)

    @field_validator(
        "nmresponsavel",
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

    @field_validator("nmorganizacao")
    @classmethod
    def normalizar_organizacao(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        return valor.strip() or None


class LeadParceiroUpdate(BaseModel):
    nmresponsavel: str | None = Field(
        default=None,
        min_length=3,
        max_length=120,
    )

    tipo: TipoParceiro | None = None

    tipovenda: TipoVendaLead | None = None

    telefone: str | None = Field(
        default=None,
        min_length=10,
        max_length=30,
    )

    email: EmailStr | None = None

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
    nmorganizacao: str | None = None
    nmestabelecimento: str

    tipo: TipoParceiro

    tipovenda: TipoVendaLead

    telefone: str
    email: str

    estado_id: int
    cidade_id: int

    nmestado: str
    sgestado: str
    nmcidade: str

    mensagem: str | None = None

    # Resumo calculado a partir dos estabelecimentos; nao e armazenado no lead.
    status: StatusLeadEstabelecimentoSchema

    dtcriacao: datetime
    dtultatu: datetime | None = None

    dias_espera: int
    aguardando_resposta: bool = False
    estabelecimentos: list[LeadEstabelecimentoOut] = Field(default_factory=list)

    class Config:
        from_attributes = True

class LeadParceiroCadastroOut(LeadParceiroOut):
    acesso_portal: str
