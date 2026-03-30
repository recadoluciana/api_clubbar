from pydantic import BaseModel
from typing import Optional


class LojaCreate(BaseModel):
    organizacao_id: int
    cidade_id: int  # 👈 obrigatório
    nmloja: str
    dsbairroloja: Optional[str] = None
    nrtelloja: Optional[str] = None
    dshorarioloja: Optional[str] = None
    nrdiavalidade: Optional[int] = None
    urllogoloja: Optional[str] = None  # 👈 novo


class LojaUpdate(BaseModel):
    organizacao_id: Optional[int] = None
    cidade_id: int  # 👈 obrigatório
    nmloja: Optional[str] = None
    dsbairroloja: Optional[str] = None
    nrtelloja: Optional[str] = None
    dshorarioloja: Optional[str] = None
    nrdiavalidade: Optional[int] = None
    urllogoloja: Optional[str] = None  # 👈 novo
