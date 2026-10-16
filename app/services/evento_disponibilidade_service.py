from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.evento import Evento


def validar_evento_unico_por_loja_data(
    db: Session,
    *,
    loja_id: int,
    inicio: datetime,
    ignorar_evento_id: int | None = None,
) -> None:
    """Impede mais de uma ocorrência ativa por loja em uma mesma data."""
    consulta = db.query(Evento).filter(
        Evento.loja_id == loja_id,
        func.date(Evento.dtinicioevento) == inicio.date(),
        Evento.statusevento != "CANCELADO",
    )
    if ignorar_evento_id is not None:
        consulta = consulta.filter(Evento.evento_id != ignorar_evento_id)

    existente = consulta.first()
    if existente:
        data = inicio.strftime("%d/%m/%Y")
        raise HTTPException(
            status_code=409,
            detail=(
                f'Já existe o evento "{existente.nmtituloevento}" para este '
                f"estabelecimento na data ({data})."
            ),
        )
