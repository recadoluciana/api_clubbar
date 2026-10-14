from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal

class ProdutoCreate(BaseModel):
    organizacao_id: int
    loja_id: int
    categoria_id: Optional[int] = None
    nmproduto: str = Field(..., min_length=1, max_length=100)
    dsproduto: Optional[str] = Field(None, max_length=255)
    sitproduto: Literal["ATIVO", "INATIVO"] = "ATIVO"
    skuproduto: Optional[str] = Field(None, max_length=100)
    idtipoproduto: Literal["I", "P"] = "P"
    lote_id: Optional[int] = None

    @field_validator("nmproduto")
    @classmethod
    def validar_nome(cls, v: str):
        v = v.strip()
        if not v:
            raise ValueError("O nome do produto é obrigatório")
        return v

class ProdutoOut(BaseModel):
    produto_id: int
    organizacao_id: int
    loja_id: int
    categoria_id: Optional[int]
    nmproduto: str
    dsproduto: Optional[str]
    sitproduto: str
    skuproduto: Optional[str]
    idtipoproduto: str
    lote_id: Optional[int]
    nmcategoria: Optional[str] = None
    urlfotoproduto: Optional[str] = None


    class Config:
        from_attributes = True

class ProdutoUpdate(BaseModel):
    categoria_id: Optional[int] = None
    nmproduto: Optional[str] = None
    dsproduto: Optional[str] = None
    sitproduto: Optional[str] = None
    skuproduto: Optional[str] = None
