from pydantic import BaseModel, Field
from typing import Optional, Literal


class AddItemIn(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int
    idtipoproduto: Literal["P", "I"]

    produto_id: Optional[int] = None
    lote_id: Optional[int] = None

    qt: int = Field(ge=1, default=1)
    obs: Optional[str] = None

    nmparticipante: str | None = None
    cpfparticipante: str | None = None

class AddItemOut(BaseModel):
    carrinho_id: int
    itcarrinho_id: int
    produto_id: int
    qt: int
    obs: Optional[str] = None
    nmparticipante: str | None = None
    cpfparticipante: str | None = None


class CarrinhoItemAgrupadoOut(BaseModel):
    carrinho_id: int
    produto_id: int
    dsobsitcar: Optional[str] = None
    qtitcarrinho: int

    nmproduto: Optional[str] = None
    vrprecoprod: Optional[float] = None
    img: Optional[str] = None


class LojaCarrinhoOut(BaseModel):
    loja_id: int
    organizacao_id: int
    nmloja: str
    dsbairroloja: Optional[str] = None
    urllogoloja: Optional[str] = None
    total_itens: int