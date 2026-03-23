from pydantic import BaseModel, Field
from typing import Optional, Literal, Union

class AddProdutoIn(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int
    idtipoproduto: Literal["P"] = "P"
    produto_id: int
    qt: int = Field(ge=1, default=1)
    obs: Optional[str] = None

class AddIngressoIn(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int
    idtipoproduto: Literal["I"] = "I"
    lote_id: int
    qt: int = Field(ge=1, default=1)
    obs: Optional[str] = None

AddItemIn = Union[AddProdutoIn, AddIngressoIn]

class AddItemOut(BaseModel):
    carrinho_id: int
    itcarrinho_id: int
    produto_id: int
    qt: int
    obs: Optional[str] = None

class CarrinhoItemAgrupadoOut(BaseModel):
    carrinho_id: int
    produto_id: int
    dsobsitcar: Optional[str] = None
    qtitcarrinho: int

    # opcionais (se fizer JOIN com produto)
    nmproduto: Optional[str] = None
    vrprecoprod: Optional[float] = None
    img: Optional[str] = None

class CarrinhoItemIn(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int
    idtipoproduto: str  # <- em vez de Literal

    produto_id: Optional[int] = None
    lote_id: Optional[int] = None
    qt: int = 1
    obs: Optional[str] = None

class LojaCarrinhoOut(BaseModel):
    loja_id: int
    organizacao_id: int
    nmloja: str
    dsbairroloja: str | None = None
    total_itens: int