from pydantic import BaseModel, Field
from typing import Literal, Optional


class LojaCreate(BaseModel):
    organizacao_id: int
    estado_id: Optional[int] = None
    cidade_id: Optional[int] = None
    nmloja: str
    nrceploja: Optional[str] = Field(default=None, min_length=1, max_length=9)
    nrendeloja: Optional[str] = Field(default=None, min_length=1, max_length=20)
    tipoloja: Optional[str] = None
    atendimentofisico: Literal[S, N] = S
    vendaprodutos: Literal[S, N] = S
    vendaingressos: Literal[S, N] = S
    dsbairroloja: Optional[str] = None
    nrtelloja: Optional[str] = None
    aberto24x7: Literal["S", "N"] = "N"
    dsestiloloja: Optional[str] = None
    nrdiavalidade: Optional[int] = None
    idvalidadeprod: Literal["S", "N"] = "S"
    urllogoloja: Optional[str] = None  # 👈 novo
    urlfachadaloja: Optional[str] = None
    qtcpdloja: Optional[int] = Field(default=None, ge=1)


class LojaUpdate(BaseModel):
    tipoloja: Optional[str] = None
    atendimentofisico: Optional[Literal[S, N]] = None
    vendaprodutos: Optional[Literal[S, N]] = None
    vendaingressos: Optional[Literal[S, N]] = None
    organizacao_id: Optional[int] = None
    estado_id: Optional[int] = None
    cidade_id: Optional[int] = None
    nmloja: Optional[str] = None
    nrceploja: Optional[str] = Field(default=None, min_length=1, max_length=9)
    nrendeloja: Optional[str] = Field(default=None, min_length=1, max_length=20)
    dsbairroloja: Optional[str] = None
    nrtelloja: Optional[str] = None
    aberto24x7: Optional[Literal["S", "N"]] = None
    dsestiloloja: Optional[str] = None
    nrdiavalidade: Optional[int] = None
    idvalidadeprod: Optional[Literal["S", "N"]] = None
    urllogoloja: Optional[str] = None  # 👈 novo
    urlfachadaloja: Optional[str] = None
    qtcpdloja: Optional[int] = Field(default=None, ge=1)
