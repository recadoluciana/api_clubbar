from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


SituacaoOrganizacao = Literal[
    "ATIVA",
    "INATIVA",
]


class OrganizacaoCreate(BaseModel):
    nmorganizacao: str = Field(..., min_length=3, max_length=120)
    rzsocialorganizacao: str = Field(..., min_length=3, max_length=160)
    cnpjorganizacao: str = Field(..., min_length=14, max_length=14)
    emailorganizacao: EmailStr
    telorganizacao: str = Field(..., min_length=10, max_length=25)
    ceporganizacao: str | None = Field(default=None, max_length=20)
    endorganizacao: str = Field(..., min_length=3, max_length=255)
    nrendorganizacao: str = Field(..., min_length=1, max_length=20)
    complorganizacao: str | None = Field(default=None, max_length=120)
    cidade_id: int = Field(..., gt=0)
    nmbairro: str | None = Field(default=None, max_length=120)
    leadparceiro_id: int | None = Field(default=None, gt=0)


class OrganizacaoUpdate(BaseModel):
    nmorganizacao: str | None = Field(
        default=None,
        min_length=3,
        max_length=120,
    )

    rzsocialorganizacao: str | None = Field(
        default=None,
        min_length=3,
        max_length=160,
    )

    cnpjorganizacao: str | None = Field(
        default=None,
        min_length=14,
        max_length=14,
    )

    emailorganizacao: EmailStr | None = None

    telorganizacao: str | None = Field(
        default=None,
        min_length=10,
        max_length=25,
    )

    ceporganizacao: str | None = Field(
        default=None,
        max_length=20,
    )

    endorganizacao: str | None = Field(
        default=None,
        min_length=3,
        max_length=255,
    )

    nrendorganizacao: str | None = Field(
        default=None,
        min_length=1,
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
    sitorganizacao: SituacaoOrganizacao


class OrganizacaoOut(BaseModel):
    organizacao_id: int

    nmorganizacao: str
    rzsocialorganizacao: str
    cnpjorganizacao: str
    emailorganizacao: str
    telorganizacao: str

    ceporganizacao: str | None = None
    endorganizacao: str
    nrendorganizacao: str
    complorganizacao: str | None = None

    cidade_id: int
    nmcidade: str | None = None
    sgestado: str | None = None

    nmbairro: str | None = None
    leadparceiro_id: int | None = None

    sitorganizacao: SituacaoOrganizacao

    dtcriacao: datetime
    dtultatu: datetime | None = None

    class Config:
        from_attributes = True