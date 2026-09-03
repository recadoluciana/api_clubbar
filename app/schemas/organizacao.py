from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


SituacaoOrganizacao = Literal['ATIVA', 'INATIVA']
TipoOperacao = Literal['BAR', 'CASA_NOTURNA', 'PRODUTOR_EVENTOS', 'CASA_EVENTOS']


class OrganizacaoCreate(BaseModel):
    nmorganizacao: str = Field(min_length=3, max_length=120)
    nmresponsavelprincipal: str | None = Field(default=None, min_length=2, max_length=120)
    emailorganizacao: EmailStr
    telorganizacao: str = Field(min_length=10, max_length=25)
    tipooperacao: TipoOperacao | None = None
    leadparceiro_id: int | None = Field(default=None, gt=0)


class OrganizacaoUpdate(BaseModel):
    nmorganizacao: str | None = Field(default=None, min_length=3, max_length=120)
    nmresponsavelprincipal: str | None = Field(default=None, min_length=2, max_length=120)
    emailorganizacao: EmailStr | None = None
    telorganizacao: str | None = Field(default=None, min_length=10, max_length=25)
    tipooperacao: TipoOperacao | None = None


class OrganizacaoSituacaoUpdate(BaseModel):
    sitorganizacao: SituacaoOrganizacao


class OrganizacaoOut(BaseModel):
    organizacao_id: int
    nmorganizacao: str
    nmresponsavelprincipal: str | None = None
    emailorganizacao: str
    telorganizacao: str
    tipooperacao: str | None = None
    leadparceiro_id: int | None = None
    nmleadorigem: str | None = None
    sitorganizacao: SituacaoOrganizacao
    dtcriacao: datetime
    dtultatu: datetime | None = None

    class Config:
        from_attributes = True
