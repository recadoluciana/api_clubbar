from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from app.models.evento import Evento


def evento_ja_aconteceu(evento: Evento, agora: datetime | None = None) -> bool:
    """Indica se a ocorrência já terminou no horário de Brasília.

    Eventos noturnos seguem editáveis depois da meia-noite enquanto ainda
    estão acontecendo. Sem um término cadastrado, aplicamos a mesma janela
    operacional de seis horas utilizada para a vigência dos ingressos.
    """
    if evento.dtinicioevento is None:
        return False
    momento = agora or datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    if momento.tzinfo is not None:
        momento = momento.replace(tzinfo=None)
    fim_evento = evento.dtfimevento or (evento.dtinicioevento + timedelta(hours=6))
    return momento >= fim_evento


def validar_evento_editavel(evento: Evento, agora: datetime | None = None) -> None:
    """Eventos encerrados ficam preservados, apenas para consulta."""
    if evento_ja_aconteceu(evento, agora):
        raise HTTPException(
            status_code=409,
            detail="Este evento já foi encerrado e está disponível somente para consulta.",
        )
