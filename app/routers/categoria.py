# app/routers/categorias.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.loja import Loja
from app.models.categoria import Categoria

router = APIRouter(prefix="/lojas", tags=["Categorias"])


@router.get("/{loja_id}/categorias")
def listar_categorias_por_loja(loja_id: int, db: Session = Depends(get_db)):

    # 1) busca loja pra saber organizacao_id
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    rows = (
        db.query(
            Categoria.categoria_id,
            Categoria.nmcategoria,
        )
        .filter(
            Categoria.organizacao_id == loja.organizacao_id,
            Categoria.loja_id == loja_id,
            Categoria.sitcategoria == "ATIVA",
        )
        .order_by(
            Categoria.idordcategoria.asc(),
            Categoria.nmcategoria.asc(),
        )
        .all()
    )
    
    # 3) monta JSON manual
    return [
        {
            "categoria_id": r.categoria_id,
            "nmcategoria": r.nmcategoria,
        }
        for r in rows
    ]
