from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import traceback

from app.database import get_db
from app.models.evento import Evento
from app.models.loja import Loja
from app.models.eventolote import EventoLote
from app.schemas.eventolote import EventoLoteCreate, EventoLoteUpdate, EventoLoteOut

router = APIRouter(prefix="/eventos", tags=["eventos"])


@router.get("/{evento_id}/lotes", response_model=list[EventoLoteOut])
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


@router.get("/{evento_id}/lotes_todos")
def listar_todos_lotes_evento(
    evento_id: int,
    db: Session = Depends(get_db),
):
    evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()

    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    lotes = (
        db.query(EventoLote)
        .filter(EventoLote.evento_id == evento_id)
        .order_by(EventoLote.lote_id.asc())
        .all()
    )

    return [
        {
            "lote_id": lote.lote_id,
            "organizacao_id": lote.organizacao_id,
            "loja_id": lote.loja_id,
            "evento_id": lote.evento_id,
            "nmlote": lote.nmlote,
            "vrprecolote": float(lote.vrprecolote or 0),
            "qttotallote": int(lote.qttotallote or 0),
            "qtvendidalote": int(lote.qtvendidalote or 0),
            "dtiniciovenda": lote.dtiniciovenda,
            "dtfimvenda": lote.dtfimvenda,
            "statuslote": lote.statuslote,
            "dtcriacao": lote.dtcriacao,
            "dtultatu": lote.dtultatu,
        }
        for lote in lotes
    ]


@router.post("/{evento_id}/lotes")
def criar_lote_evento(
    evento_id: int,
    data: EventoLoteCreate,
    db: Session = Depends(get_db),
):
    try:
        evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()
        if not evento:
            raise HTTPException(status_code=404, detail="Evento não encontrado")

        loja = db.query(Loja).filter(Loja.loja_id == data.loja_id).first()
        if not loja:
            raise HTTPException(status_code=404, detail="Loja não encontrada")

        novo = EventoLote(
            organizacao_id=data.organizacao_id,
            loja_id=data.loja_id,
            evento_id=evento_id,
            nmlote=data.nmlote,
            vrprecolote=data.vrprecolote,
            qttotallote=data.qttotallote,
            qtvendidalote=data.qtvendidalote if data.qtvendidalote is not None else 0,
            dtiniciovenda=data.dtiniciovenda,
            dtfimvenda=data.dtfimvenda,
            statuslote=data.statuslote if data.statuslote else "ATIVO",
        )

        db.add(novo)
        db.commit()
        db.refresh(novo)

        return {
            "mensagem": "Lote cadastrado com sucesso",
            "lote_id": novo.lote_id,
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao criar lote: {str(e)}")


@router.put("/lotes/{lote_id}")
def atualizar_lote_evento(
    lote_id: int,
    data: EventoLoteUpdate,
    db: Session = Depends(get_db),
):
    try:
        lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado")

        if data.organizacao_id is not None:
            lote.organizacao_id = data.organizacao_id

        if data.loja_id is not None:
            loja = db.query(Loja).filter(Loja.loja_id == data.loja_id).first()
            if not loja:
                raise HTTPException(status_code=404, detail="Loja não encontrada")
            lote.loja_id = data.loja_id

        if data.evento_id is not None:
            evento = db.query(Evento).filter(Evento.evento_id == data.evento_id).first()
            if not evento:
                raise HTTPException(status_code=404, detail="Evento não encontrado")
            lote.evento_id = data.evento_id

        if data.nmlote is not None:
            lote.nmlote = data.nmlote

        if data.vrprecolote is not None:
            lote.vrprecolote = data.vrprecolote

        if data.qttotallote is not None:
            lote.qttotallote = data.qttotallote

        if data.qtvendidalote is not None:
            lote.qtvendidalote = data.qtvendidalote

        if data.dtiniciovenda is not None:
            lote.dtiniciovenda = data.dtiniciovenda

        if data.dtfimvenda is not None:
            lote.dtfimvenda = data.dtfimvenda

        if data.statuslote is not None:
            lote.statuslote = data.statuslote

        db.commit()
        db.refresh(lote)

        return {
            "mensagem": "Lote atualizado com sucesso",
            "lote": {
                "lote_id": lote.lote_id,
                "organizacao_id": lote.organizacao_id,
                "loja_id": lote.loja_id,
                "evento_id": lote.evento_id,
                "nmlote": lote.nmlote,
                "vrprecolote": float(lote.vrprecolote or 0),
                "qttotallote": int(lote.qttotallote or 0),
                "qtvendidalote": int(lote.qtvendidalote or 0),
                "dtiniciovenda": lote.dtiniciovenda,
                "dtfimvenda": lote.dtfimvenda,
                "statuslote": lote.statuslote,
                "dtcriacao": lote.dtcriacao,
                "dtultatu": lote.dtultatu,
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar lote: {str(e)}")


@router.delete("/lotes/{lote_id}")
def deletar_lote_evento(
    lote_id: int,
    db: Session = Depends(get_db),
):
    try:
        lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado")

        if int(lote.qtvendidalote or 0) > 0:
            raise HTTPException(
                status_code=400,
                detail="Não é possível excluir o lote, pois já existem vendas vinculadas"
            )

        db.delete(lote)
        db.commit()

        return {"mensagem": "Lote deletado com sucesso"}

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar lote: {str(e)}")