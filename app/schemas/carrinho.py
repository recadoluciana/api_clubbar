from pydantic import BaseModel, Field
from typing import Optional

class AddItemIn(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int
    produto_id: int
    qt: int = Field(default=1, ge=1)
    obs: Optional[str] = None
    idtipoproduto: str = 'PRODUTO'

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
