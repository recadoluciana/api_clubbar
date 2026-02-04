from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.categoria import Categoria
from app.models.produto import Produto

router = APIRouter(tags=["Produtos"])


@router.get("/lojas/{loja_id}/produtos")
def listar_produtos_por_loja(loja_id: int, db: Session = Depends(get_db)):

    rows = (
        db.query(
            Produto.organizacao_id,
            Produto.loja_id,
            Produto.produto_id,
            Produto.categoria_id,
            Produto.nmproduto,
            Produto.dsproduto,
            Produto.vrprecoprod,
            Produto.sitproduto,
            Produto.skuproduto,
            Categoria.nmcategoria
        )
        .join(Categoria, Categoria.categoria_id == Produto.categoria_id)
        .filter(
            Produto.loja_id == loja_id,
            Produto.sitproduto == "ATIVO",
        )
        .order_by(
            Categoria.nmcategoria,   # ✅ primeiro por categoria
            Produto.nmproduto        # ✅ depois por nome
        )
        .all()
    )

    return [
        {
            "organizacao_id": organizacao_id,
            "loja_id": loja_id,
            "produto_id": produto_id,
            "categoria_id": categoria_id,
            "nmcategoria": nmcategoria,   # ✅ nome da categoria
            "nmproduto": nmproduto,
            "dsproduto": dsproduto,
            "vrprecoprod": float(vrprecoprod),
            "sitproduto": sitproduto,
            "skuproduto": skuproduto,
        }
        for (
            organizacao_id,
            loja_id,
            produto_id,
            categoria_id,
            nmproduto,
            dsproduto,
            vrprecoprod,
            sitproduto,
            skuproduto,
            nmcategoria
        ) in rows
    ]
