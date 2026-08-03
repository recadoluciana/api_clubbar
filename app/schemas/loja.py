from pydantic import BaseModel
from typing import Literal, Optional


class LojaCreate(BaseModel):
    organizacao_id: int
    estado_id: int
    cidade_id: int  # 👈 obrigatório
    nmloja: str
    dsbairroloja: Optional[str] = None
    nrtelloja: Optional[str] = None
    dshorarioloja: Optional[str] = None
    aberto24x7: Literal["S", "N"] = "N"
    dsestiloloja: Optional[str] = None
    nrdiavalidade: Optional[int] = None
    idvalidadeprod: Literal["S", "N"] = "S"
    urllogoloja: Optional[str] = None  # 👈 novo
    urlfachadaloja: Optional[str] = None


class LojaUpdate(BaseModel):
    organizacao_id: Optional[int] = None
    estado_id: Optional[int] = None
    cidade_id: Optional[int] = None
    nmloja: Optional[str] = None
    dsbairroloja: Optional[str] = None
    nrtelloja: Optional[str] = None
    dshorarioloja: Optional[str] = None
    aberto24x7: Optional[Literal["S", "N"]] = None
    dsestiloloja: Optional[str] = None
    nrdiavalidade: Optional[int] = None
    idvalidadeprod: Optional[Literal["S", "N"]] = None
    urllogoloja: Optional[str] = None  # 👈 novo
    urlfachadaloja: Optional[str] = None
