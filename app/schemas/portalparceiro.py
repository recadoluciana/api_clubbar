#portalparceiro.py
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator
from app.utils.documento import normalizar_cpf_cnpj


class PortalMensagemCreate(BaseModel):
    mensagem: str = Field(min_length=1, max_length=3000)


class PortalLoginLead(BaseModel):
    email: EmailStr
    telefone: str = Field(min_length=10, max_length=30)


class PortalSolicitarCodigo(BaseModel):
    documento: str = Field(min_length=11, max_length=25)
    email: EmailStr | None = None


class PortalConfirmarCodigo(PortalSolicitarCodigo):
    codigo: str = Field(pattern=r"^[0-9]{8}$")


class PortalRecuperarDados(BaseModel):
    email: EmailStr


class PortalAgendamentoResposta(BaseModel):
    status: Literal["CONFIRMADO", "RECUSADO"]


class PortalStatusUpdate(BaseModel):
    leadestabelecimento_id: int | None = Field(default=None, gt=0)
    status: Literal["NEGOCIANDO", "ACEITOU_PARCERIA", "RECUSOU_PARCERIA"]


class PortalEstabelecimentoCreate(BaseModel):
    nmestabelecimento: str = Field(min_length=2, max_length=160)
    nmresponsavel: str | None = Field(default=None, max_length=120)
    telefone_responsavel: str | None = Field(default=None, max_length=30)
    email_responsavel: EmailStr | None = None
    tipo: Literal["BAR", "CASA_NOTURNA", "PRODUTOR_EVENTOS", "CASA_EVENTOS", "RESTAURANTE", "CONVENIENCIA"]
    tipovenda: Literal["PRODUTOS", "INGRESSOS", "AMBOS"] = "AMBOS"
    cpfcnpj: str | None = Field(default=None, max_length=18)
    telefone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = None
    estado_id: int = Field(gt=0)
    cidade_id: int = Field(gt=0)
    cep: str = Field(pattern=r"^\d{8}$")
    endereco: str = Field(min_length=1, max_length=255)
    numero: str = Field(min_length=1, max_length=20)
    complemento: str | None = Field(default=None, max_length=120)
    bairro: str = Field(min_length=1, max_length=120)
    mensagem: str | None = Field(default=None, max_length=1000)


class PortalEstabelecimentoUpdate(BaseModel):
    nmestabelecimento: str | None = Field(default=None, min_length=2, max_length=160)
    nmresponsavel: str | None = Field(default=None, max_length=120)
    telefone_responsavel: str | None = Field(default=None, max_length=30)
    email_responsavel: EmailStr | None = None
    tipo: Literal["BAR", "CASA_NOTURNA", "PRODUTOR_EVENTOS", "CASA_EVENTOS", "RESTAURANTE", "CONVENIENCIA"]
    tipovenda: Literal["PRODUTOS", "INGRESSOS", "AMBOS"]
    cpfcnpj: str | None = Field(default=None, max_length=18)
    estado_id: int = Field(gt=0)
    cidade_id: int = Field(gt=0)
    cep: str = Field(pattern=r"^\d{8}$")
    endereco: str = Field(min_length=1, max_length=255)
    numero: str = Field(min_length=1, max_length=20)
    complemento: str | None = Field(default=None, max_length=120)
    bairro: str = Field(min_length=1, max_length=120)

    @field_validator("nmestabelecimento")
    @classmethod
    def validar_nome(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        if len(valor) < 2:
            raise ValueError("Informe o nome com pelo menos dois caracteres.")
        return valor

    @field_validator("cpfcnpj")
    @classmethod
    def normalizar_documento(cls, valor: str | None) -> str | None:
        if not valor:
            return None
        return normalizar_cpf_cnpj(valor)

    @field_validator("telefone_responsavel", "cep", mode="before")
    @classmethod
    def somente_numeros(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        numeros = "".join(caractere for caractere in str(valor) if caractere.isdigit())
        return numeros or None
