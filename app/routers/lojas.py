# app/routers/lojas.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.loja import Loja
from app.models.organizacao import Organizacao

router = APIRouter(prefix="/lojas", tags=["Lojas"])

@router.get("")
def listar_lojas(db: Session = Depends(get_db)):
    rows = (
        db.query(
            Loja.loja_id,
            Loja.organizacao_id,
            Organizacao.nmorganizacao,
            Loja.nmloja,
            Loja.endloja,
            Loja.aberto24x7,
            Loja.dshorarioloja,
            Loja.nrtelloja,
        )
        .join(Organizacao, Organizacao.organizacao_id == Loja.organizacao_id)
        .filter(Loja.sitloja == "ATIVA")
        .order_by(Organizacao.nmorganizacao, Loja.nmloja)
        .all()
    )

    return [
        {
            "loja_id": r.loja_id,
            "organizacao_id": r.organizacao_id,
            "nmorganizacao": r.nmorganizacao,
            "nmloja": r.nmloja,
            "endloja": r.endloja,
            "aberto24x7": r.aberto24x7,
            "dshorarioloja": r.dshorarioloja,
            "nrtelloja": r.nrtelloja,
        }
        for r in rows
    ]
