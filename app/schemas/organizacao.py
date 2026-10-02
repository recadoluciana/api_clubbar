from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


SituacaoOrganizacao = Literal['ATIVA', 'INATIVA']
class OrganizacaoCreate(BaseModel):
    nmorganizacao: str = Field(min_length=3, max_length=120)
    nmresponsavelprincipal: str | None = Field(default=None, min_length=2, max_length=120)
    emailorganizacao: EmailStr
    telorganizacao: str = Field(min_length=10, max_length=25)
    leadparceiro_id: int | None = Field(default=None, gt=0)

    @field_validator('emailorganizacao', mode='before')
    @classmethod
    def validar_tamanho_email(cls, valor):
        email = str(valor).strip().lower()
        if len(email) > 254:
            raise ValueError('O e-mail deve ter no máximo 254 caracteres.')
        return email


class OrganizacaoUpdate(BaseModel):
    nmorganizacao: str | None = Field(default=None, min_length=3, max_length=120)
    nmresponsavelprincipal: str | None = Field(default=None, min_length=2, max_length=120)
    emailorganizacao: EmailStr | None = None
    telorganizacao: str | None = Field(default=None, min_length=10, max_length=25)

    @field_validator('emailorganizacao', mode='before')
    @classmethod
    def validar_tamanho_email(cls, valor):
        if valor is None:
            return valor
        email = str(valor).strip().lower()
        if len(email) > 254:
            raise ValueError('O e-mail deve ter no máximo 254 caracteres.')
        return email


class OrganizacaoSituacaoUpdate(BaseModel):
    sitorganizacao: SituacaoOrganizacao


class OrganizacaoOut(BaseModel):
    organizacao_id: int
    nmorganizacao: str
    nmresponsavelprincipal: str | None = None
    emailorganizacao: str
    telorganizacao: str
    leadparceiro_id: int | None = None
    nmleadorigem: str | None = None
    sitorganizacao: SituacaoOrganizacao
    dtcriacao: datetime
    dtultatu: datetime | None = None

    class Config:
        from_attributes = True
