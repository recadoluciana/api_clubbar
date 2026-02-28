from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.eventolote import EventoLote
from app.schemas.eventolote import EventoLoteOut

router = APIRouter(prefix="/eventos", tags=["eventos"])


@router.get("/{evento_id}/lotes",response_model=list[EventoLoteOut],)
def listar_lotes_evento(
    evento_id: int,
    db: Session = Depends(get_db),
):
    agora = datetime.now()

    lotes = (
        db.query(EventoLote)
        .filter(EventoLote.evento_id == evento_id)
        .filter(EventoLote.statuslote == "ATIVO")
        .filter(
            (EventoLote.dtiniciovenda == None)  # noqa: E711
            | (EventoLote.dtiniciovenda <= agora)
        )
        .filter(
            (EventoLote.dtfimvenda == None)  # noqa: E711
            | (EventoLote.dtfimvenda >= agora)
        )
        .order_by(EventoLote.vrprecolote.asc())
        .all()
    )

    return lotes