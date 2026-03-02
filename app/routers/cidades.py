# app/routers/cidades.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db

from app.models.cidade import Cidade
from app.models.estado import Estado  # ajuste o import conforme seu projeto

router = APIRouter(prefix="/cidades", tags=["Cidades"])


@router.get("")
def listar_cidades(
    pais_id: int | None = Query(default=None),
    estado_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Cidade, Estado)
        .join(Estado, Estado.estado_id == Cidade.estado_id)
    )

    if pais_id:
        q = q.filter(Cidade.pais_id == pais_id)
    if estado_id:
        q = q.filter(Cidade.estado_id == estado_id)

    q = q.order_by(Estado.sgestado.asc(), Cidade.nmcidade.asc())  # ajuste sgestado/sguf

    rows = q.all()

    out = []
    for cidade, estado in rows:
        sg = getattr(estado, "sgestado", None) or getattr(estado, "sguf", None) or ""
        out.append({
            "cidade_id": cidade.cidade_id,
            "pais_id": cidade.pais_id,
            "estado_id": cidade.estado_id,
            "nmcidade": cidade.nmcidade,
            "sgestado": sg,
            "label": f"{cidade.nmcidade} - {sg}".strip(" -"),
        })
    return out