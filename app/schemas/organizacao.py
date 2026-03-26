# app/schemas/organizacao.py

from pydantic import BaseModel, EmailStr
from typing import Optional

from typing import Literal


class OrganizacaoCreate(BaseModel):
    nmorganizacao: str
    cnpjorganizacao: Optional[str] = None
    
class OrganizacaoUpdate(BaseModel):
    nmorganizacao: Optional[str] = None
    cnpjorganizacao: Optional[str] = None
    emailorganizacao: Optional[str] = None
    telorganizacao: Optional[str] = None
    sitorganizacao: Optional[str] = None
