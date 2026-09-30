from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.evento import Evento


def _normalizar_local(local: str | None) -> str:
    return (local or "").strip().lower()


def validar_evento_unico_por_loja_data_local(
    db: Session,
    *,
    loja_id: int,
    inicio: datetime,
    local: str | None,
    ignorar_evento_id: int | None = None,
) -> None:
    """Impede duas ocorrências ativas para a mesma loja, data e local."""
    consulta = db.query(Evento).filter(
        Evento.loja_id == loja_id,
        func.date(Evento.dtinicioevento) == inicio.date(),
        Evento.statusevento != "CANCELADO",
        func.lower(func.trim(func.coalesce(Evento.nmlocalevento, "")))
        == _normalizar_local(local),
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
                f"estabelecimento, local e data ({data})."
            ),
        )
