# app/routers/eventos.py
from datetime import datetime, time
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm import joinedload

from typing import Optional
from fastapi import Query

from app.database import get_db
from app.models.loja import Loja
from app.models.evento import Evento
from app.models.cidade import Cidade
from app.schemas.evento import EventoOutBR, ListaEventoIn
from app.models.eventolote import EventoLote
from app.schemas.eventolote import EventoLoteOut 

from app.utils.datetime_utils import formatar_data_br

router = APIRouter(prefix="/eventos", tags=["eventos"])

def evento_to_out_br(ev: Evento, nmloja: str | None = None, nmcidade: str | None = None):
    return {
        "evento_id": ev.evento_id,
        "organizacao_id": ev.organizacao_id,
        "loja_id": ev.loja_id,
        "produto_id_ingresso": ev.produto_id_ingresso,

        "nmtituloevento": ev.nmtituloevento,
        "dsdescevento": ev.dsdescevento,

        "dtinicioevento": ev.dtinicioevento,
        "dtfimevento": ev.dtfimevento,

        "nmlocalevento": ev.nmlocalevento,
        "dsendlocevento": ev.dsendlocevento,
        "urlbannerevento": ev.urlbannerevento,

        "statusevento": ev.statusevento,

        "nmloja": nmloja,
        "nmcidade": nmcidade,
    }


def hoje_inicio_br() -> datetime:
    tz = ZoneInfo("America/Sao_Paulo")
    return datetime.combine(datetime.now(tz).date(), time.min).replace(tzinfo=None)


@router.get("/lojas/{organizacao_id}/{loja_id}/proximos", response_model=list[EventoOutBR])
def listar_eventos_proximos(
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
):
    hi = hoje_inicio_br()

    eventos = (
        db.query(Evento, Loja.nmloja, Cidade.nmcidade)
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .join(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .filter(Evento.organizacao_id == organizacao_id)
        .filter(Evento.loja_id == loja_id)
        .filter(Evento.statusevento == "ATIVO")
        .filter(Evento.dtinicioevento >= hi)
        .order_by(Evento.dtinicioevento.asc())
    )

    return [evento_to_out_br(ev, nmloja, nmcidade) for ev, nmloja, nmcidade in eventos]


@router.get("/proximos", response_model=list[EventoOutBR])
def listar_eventos_proximos_global(
    cidade_id: int | None = None,
    db: Session = Depends(get_db),
):
    hi = hoje_inicio_br()

    q = (
        db.query(Evento, Loja.nmloja, Cidade.nmcidade)
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .join(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .filter(Evento.statusevento == "ATIVO")
        .filter(Evento.dtinicioevento >= hi)
    )

    if cidade_id:
        q = q.filter(Loja.cidade_id == cidade_id)

    eventos = q.order_by(Evento.dtinicioevento.asc()).all()

    return [evento_to_out_br(ev, nmloja, nmcidade) for ev, nmloja, nmcidade in eventos]

@router.get("/{evento_id}")
def get_evento_por_id(evento_id: int, db: Session = Depends(get_db)):

    evento = (
        db.query(Evento, Loja.nmloja, Cidade.nmcidade)
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .join(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .filter(Evento.evento_id == evento_id)
        .first()
    )

    print("passei aqui no get_evento_por_id")

    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    evento_obj, nmloja, nmcidade = evento

    # buscar lotes
    lotes = (
        db.query(EventoLote)
        .filter(EventoLote.evento_id == evento_id)
        .order_by(EventoLote.lote_id.asc())
        .all()
    )

    return {
        "evento_id": evento_obj.evento_id,
        "nmtituloevento": getattr(evento_obj, "nmtituloevento", None),
        "dtinicioevento": getattr(evento_obj, "dtinicioevento", None),
        "nmlocalevento": getattr(evento_obj, "nmlocalevento", None),
        "dsendlocevento": getattr(evento_obj, "dsendlocevento", None),
        "dsdescevento": getattr(evento_obj, "dsdescevento", None),
        "urlbannerevento": getattr(evento_obj, "urlbannerevento", None),

        # ✅ novos campos
        "nmloja": nmloja,
        "nmcidade": nmcidade,

        "lotes": [
            {
                "lote_id": lista_lotes.lote_id,
                "nmlote": getattr(lista_lotes, "nmlote", None),
                "vrprecolote": float(getattr(lista_lotes, "vrprecolote", 0) or 0),
                "qttotallote": int(getattr(lista_lotes, "qttotallote", 0) or 0),
                "qtvendidalote": int(getattr(lista_lotes, "qtvendidalote", 0) or 0),
                "statuslote": getattr(lista_lotes, "statuslote", None),
            }
            for lista_lotes in lotes
        ],
    }