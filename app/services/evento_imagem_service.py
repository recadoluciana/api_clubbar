from sqlalchemy.orm import Session

from app.models.atracao import Atracao
from app.models.evento import Evento
from app.models.eventoatracao import EventoAtracao
from app.models.eventomodelo import EventoModelo
from app.models.eventomodeloatracao import EventoModeloAtracao


def imagem_evento(db: Session, evento: Evento) -> str | None:
    banner = (evento.urlbannerevento or "").strip()
    if banner:
        return banner
    resultado = (
        db.query(Atracao.urlbanneratracao)
        .join(EventoAtracao, EventoAtracao.atracao_id == Atracao.atracao_id)
        .filter(
            EventoAtracao.evento_id == evento.evento_id,
            Atracao.urlbanneratracao.isnot(None),
            Atracao.urlbanneratracao != "",
        )
        .order_by(EventoAtracao.dtinicioatracao, EventoAtracao.eventoatracao_id)
        .first()
    )
    return resultado[0] if resultado else None


def imagem_evento_modelo(db: Session, modelo: EventoModelo) -> str | None:
    banner = (modelo.urlbannerevento or "").strip()
    if banner:
        return banner
    resultado = (
        db.query(Atracao.urlbanneratracao)
        .join(EventoModeloAtracao, EventoModeloAtracao.atracao_id == Atracao.atracao_id)
        .filter(
            EventoModeloAtracao.eventomodelo_id == modelo.eventomodelo_id,
            Atracao.urlbanneratracao.isnot(None),
            Atracao.urlbanneratracao != "",
        )
        .order_by(EventoModeloAtracao.ordem, EventoModeloAtracao.nrminutoinicio)
        .first()
    )
    return resultado[0] if resultado else None
