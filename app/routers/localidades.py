# app/routers/localidades.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cidade import Cidade
from app.models.estado import Estado

router = APIRouter(prefix="/localidades", tags=["Localidades"])

@router.get("/estados")
def listar_estados(db: Session = Depends(get_db)):
    estados = db.query(Estado).order_by(Estado.nmestado.asc()).all()
    return [
        {
            "estado_id": estado.estado_id,
            "cdibgeest": estado.cdibgeest,
            "sgestado": estado.sgestado,
            "nmestado": estado.nmestado,
        }
        for estado in estados
    ]

@router.get("/estados/{estado_id}/cidades")
def listar_cidades_por_estado(estado_id: int, db: Session = Depends(get_db)):
    estado = db.query(Estado).filter(Estado.estado_id == estado_id).first()
    if not estado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Estado não encontrado.",
        )

    cidades = (
        db.query(Cidade)
        .filter(Cidade.estado_id == estado_id)
        .order_by(Cidade.nmcidade.asc())
        .all()
    )

    return [
        {
            "cidade_id": cidade.cidade_id,
            "cdibgecid": cidade.cdibgecid,
            "estado_id": cidade.estado_id,
            "nmcidade": cidade.nmcidade,
        }
        for cidade in cidades
    ]
