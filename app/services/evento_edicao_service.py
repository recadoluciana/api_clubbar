from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.models.evento import Evento


def evento_ja_aconteceu(evento: Evento) -> bool:
    """Indica se a data de início da ocorrência já ficou para trás no Brasil."""
    if evento.dtinicioevento is None:
        return False
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    return evento.dtinicioevento.date() < hoje


def validar_evento_editavel(evento: Evento) -> None:
    """Eventos de datas anteriores ficam preservados, apenas para consulta."""
    if evento_ja_aconteceu(evento):
        raise HTTPException(
            status_code=409,
            detail="Este evento já aconteceu e está disponível somente para consulta.",
        )
