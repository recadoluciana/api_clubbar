# app/schemas/organizacao.py

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


SituacaoOrganizacao = Literal[
    "ATIVA",
    "INATIVA",
]


class OrganizacaoCreate(BaseModel):
    nmorganizacao: str = Field(
        ...,
        min_length=3,
        max_length=120,
    )

    rzsocialorganizacao: str | None = Field(
        default=None,
        max_length=160,
    )

    cnpjorganizacao: str | None = Field(
        default=None,
        max_length=18,
    )

    emailorganizacao: EmailStr | None = None

    telorganizacao: str | None = Field(
        default=None,
        max_length=25,
    )

    ceporganizacao: str | None = Field(
        default=None,
        max_length=20,
    )

    endorganizacao: str | None = Field(
        default=None,
        max_length=255,
    )

    nrendorganizacao: str | None = Field(
        default=None,
        max_length=20,
    )

    complorganizacao: str | None = Field(
        default=None,
        max_length=120,
    )

    cidade_id: int | None = Field(
        default=None,
        gt=0,
    )

    nmbairro: str | None = Field(
        default=None,
        max_length=120,
    )


class OrganizacaoUpdate(BaseModel):
    """
    Atualização feita pelo Clubbar Partner.

    A situação da organização não está presente neste
    schema porque o parceiro não pode ativar ou inativar
    sua própria organização.
    """

    nmorganizacao: str | None = Field(
        default=None,
        min_length=3,
        max_length=120,
    )

    rzsocialorganizacao: str | None = Field(
        default=None,
        max_length=160,
    )

    cnpjorganizacao: str | None = Field(
        default=None,
        max_length=18,
    )

    emailorganizacao: EmailStr | None = None

    telorganizacao: str | None = Field(
        default=None,
        max_length=25,
    )

    ceporganizacao: str | None = Field(
        default=None,
        max_length=20,
    )

    endorganizacao: str | None = Field(
        default=None,
        max_length=255,
    )

    nrendorganizacao: str | None = Field(
        default=None,
        max_length=20,
    )

    complorganizacao: str | None = Field(
        default=None,
        max_length=120,
    )

    cidade_id: int | None = Field(
        default=None,
        gt=0,
    )

    nmbairro: str | None = Field(
        default=None,
        max_length=120,
    )


class OrganizacaoSituacaoUpdate(BaseModel):
    """
    Uso exclusivo do Clubbar Administrator.

    Este schema não deve ser utilizado nas rotas
    acessíveis pelo parceiro.
    """

    sitorganizacao: SituacaoOrganizacao


class OrganizacaoOut(BaseModel):
    organizacao_id: int

    nmorganizacao: str
    rzsocialorganizacao: str | None = None

    cnpjorganizacao: str | None = None
    emailorganizacao: str | None = None
    telorganizacao: str | None = None

    ceporganizacao: str | None = None
    endorganizacao: str | None = None
    nrendorganizacao: str | None = None
    complorganizacao: str | None = None

    cidade_id: int | None = None

    # Dados complementares obtidos através dos JOINs.
    nmcidade: str | None = None
    sgestado: str | None = None

    nmbairro: str | None = None

    leadparceiro_id: int | None = None

    sitorganizacao: SituacaoOrganizacao

    dtcriacao: datetime
    dtultatu: datetime | None = None

    class Config:
        from_attributes = True