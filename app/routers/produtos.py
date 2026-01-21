from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.loja import Loja
from app.models.produto import Produto

router = APIRouter(tags=["Produtos"])

@router.get("/lojas/{loja_id}/produtos")
def listar_produtos_por_loja(loja_id: int, db: Session = Depends(get_db)):

    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada.")

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
        )
        .filter(
            Produto.loja_id        == loja_id,
            Produto.organizacao_id == loja.organizacao_id,
            Produto.sitproduto     == "ATIVO",
        )
        .order_by(Produto.nmproduto)
        .all()
    )

    return [
        {
            "organizacao_id": r.organizacao_id,
            "loja_id": r.loja_id,
            "produto_id": r.produto_id,
            "categoria_id": r.categoria_id,
            "nmproduto": r.nmproduto,
            "dsproduto": r.dsproduto,
            "vrprecoprod": float(r.vrprecoprod),
            "sitproduto": r.sitproduto,
            "skuproduto": r.skuproduto,
        }
        for r in rows
    ]
