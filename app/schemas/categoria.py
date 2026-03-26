from pydantic import BaseModel
from typing import Optional

class CategoriaCreate(BaseModel):
    organizacao_id: int
    loja_id: int
    nmcategoria: str
    sitcategoria: Optional[str] = "ATIVA"
    idordcategoria: Optional[int] = 1