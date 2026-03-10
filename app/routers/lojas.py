# app/routers/lojas.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.loja import Loja
from app.models.cidade import Cidade
from app.models.organizacao import Organizacao

router = APIRouter(prefix="/lojas", tags=["Lojas"])

@router.get("")
def listar_lojas(cidade_id: int | None = None, db: Session = Depends(get_db)):
   
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
        .order_by(Loja.nmloja)
    )
    if cidade_id:
        rows = rows.filter(Loja.cidade_id == cidade_id)

    lojas = rows.order_by(Loja.nmloja.asc()).all()

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

@router.get("/dados_loja/{loja_id}")
def dados_loja(loja_id: int, db: Session = Depends(get_db)):
   
    row = (
        db.query(
            Loja.loja_id,
            Loja.organizacao_id,
            Organizacao.nmorganizacao,
            Cidade.nmcidade,
            Loja.nmloja,
            Loja.endloja,
            Loja.dsbairroloja,
            Loja.aberto24x7,
            Loja.dshorarioloja,
            Loja.nrtelloja,
            Loja.dsinstaloja,
            Loja.dsrefeloja,
            Loja.cidade_id,
        )
        .join(Organizacao, Organizacao.organizacao_id == Loja.organizacao_id)
        .outerjoin(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .filter(Loja.loja_id == loja_id)
        .first()
    )

    if not row:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    return {
        "loja_id"         : row.loja_id,
        "organizacao_id"  : row.organizacao_id,
        "nmorganizacao"   : row.nmorganizacao,
        "nmloja"          : row.nmloja,
        "endloja"         : row.endloja,
        "dsbairroloja"    : row.dsbairroloja,
        "aberto24x7"      : row.aberto24x7,
        "dshorarioloja"   : row.dshorarioloja,
        "nrtelloja"       : row.nrtelloja,
        "dsinstaloja"     : row.dsinstaloja,
        "dsrefeloja"      : row.dsrefeloja,
        "cidade_id"       : row.cidade_id,
        "nmcidade"        : row.nmcidade,
    }
