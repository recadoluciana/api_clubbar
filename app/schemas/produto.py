from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal
from decimal import Decimal

class ProdutoCreate(BaseModel):
    organizacao_id: int
    loja_id: int
    categoria_id: Optional[int] = None
    nmproduto: str = Field(..., min_length=1, max_length=100)
    dsproduto: Optional[str] = Field(None, max_length=255)
    vrprecoprod: Decimal
    sitproduto: Literal["ATIVO", "INATIVO"] = "ATIVO"
    skuproduto: Optional[str] = Field(None, max_length=100)
    idtipoproduto: Literal["I", "P"] = "P"
    lote_id: Optional[int] = None
    tipodesconto: Optional[str] = "NENHUM"
    vrdesconto: Optional[Decimal] = Decimal("0.00")
    dtinidesconto: Optional[datetime] = None
    dtfimdesconto: Optional[datetime] = None

    @field_validator("nmproduto")
    @classmethod
    def validar_nome(cls, v: str):
        v = v.strip()
        if not v:
            raise ValueError("O nome do produto é obrigatório")
        return v

    @field_validator("vrprecoprod")
    @classmethod
    def validar_preco(cls, v: Decimal):
        if v <= 0:
            raise ValueError("O preço deve ser maior que zero")
        return v

class ProdutoOut(BaseModel):
    produto_id: int
    organizacao_id: int
    loja_id: int
    categoria_id: Optional[int]
    nmproduto: str
    dsproduto: Optional[str]
    vrprecoprod: Decimal
    sitproduto: str
    skuproduto: Optional[str]
    idtipoproduto: str
    lote_id: Optional[int]
    nmcategoria: Optional[str] = None
    urlfotoproduto: Optional[str] = None

    tipodesconto: str = "NENHUM"
    vrdesconto: Decimal = Decimal("0.00")
    dtinidesconto: Optional[datetime] = None
    dtfimdesconto: Optional[datetime] = None
    vrprecofinal: Decimal
    descontoativo: bool

    class Config:
        from_attributes = True

    class Config:
        from_attributes = True

class ProdutoUpdate(BaseModel):
    categoria_id: Optional[int] = None
    nmproduto: Optional[str] = None
    dsproduto: Optional[str] = None
    vrprecoprod: Optional[float] = None
    sitproduto: Optional[str] = None
    skuproduto: Optional[str] = None
    tipodesconto: Optional[str] = None
    vrdesconto: Optional[Decimal] = None
    dtinidesconto: Optional[datetime] = None
    dtfimdesconto: Optional[datetime] = None
