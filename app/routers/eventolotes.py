from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import traceback

from app.database import get_db
from app.core.security import get_usuario_logado
from app.core.permissoes_loja import validar_mutacao_loja
from app.models.evento import Evento
from app.models.loja import Loja
from app.models.eventolote import EventoLote
from app.models.eventosetor import EventoSetor
from app.schemas.eventolote import EventoLoteCreate, EventoLoteUpdate, EventoLoteOut
from app.models.venda import Venda
from app.models.itvenda import ItVenda

router = APIRouter(prefix="/eventos", tags=["eventos"])


@router.get("/{evento_id}/lotes", response_model=list[EventoLoteOut])
def listar_lotes_evento(
    evento_id: int,
    db: Session = Depends(get_db),
):

    lotes = (
        db.query(EventoLote)
        .filter(EventoLote.evento_id == evento_id)
        .filter(EventoLote.statuslote == "ATIVO")
        .outerjoin(EventoSetor, EventoSetor.eventosetor_id == EventoLote.eventosetor_id)
        .order_by(EventoLote.nrlote.asc(), EventoSetor.nrordem.asc(), EventoLote.tipoingresso.asc())
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
        .outerjoin(EventoSetor, EventoSetor.eventosetor_id == EventoLote.eventosetor_id)
        .order_by(EventoLote.nrlote.asc(), EventoSetor.nrordem.asc(), EventoLote.tipoingresso.asc())
        .all()
    )

    return [
        {
            "lote_id": lote.lote_id,
            "organizacao_id": lote.organizacao_id,
            "loja_id": lote.loja_id,
            "evento_id": lote.evento_id,
            "nmlote": lote.nmlote,
            "eventosetor_id": lote.eventosetor_id,
            "nmsetor": lote.nmsetor,
            "nrlote": lote.nrlote,
            "tipoingresso": lote.tipoingresso,
            "vrprecolote": float(lote.vrprecolote or 0),
            "qttotallote": lote.qttotallote,
            "qtvendidalote": lote.qtvendidalote,
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
    usuario: dict = Depends(get_usuario_logado),
):
    try:
        evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()
        if not evento:
            raise HTTPException(status_code=404, detail="Evento não encontrado")
        validar_mutacao_loja(usuario, evento.organizacao_id, evento.loja_id)

        loja = db.query(Loja).filter(Loja.loja_id == data.loja_id).first()
        if not loja:
            raise HTTPException(status_code=404, detail="Loja não encontrada")
        setor = None
        if data.eventosetor_id is not None:
            setor = db.query(EventoSetor).filter(EventoSetor.eventosetor_id == data.eventosetor_id, EventoSetor.evento_id == evento_id).first()
            if not setor: raise HTTPException(status_code=404, detail="Setor do evento não encontrado")
        capacidade = setor.qtcapacidade if setor else loja.qtcpdloja
        if not capacidade or capacidade <= 0:
            raise HTTPException(status_code=422, detail="Informe a capacidade do setor ou do estabelecimento")
        filtro_capacidade = [EventoLote.evento_id == evento_id]
        if setor:
            filtro_capacidade.append(EventoLote.eventosetor_id == setor.eventosetor_id)
        else:
            filtro_capacidade.append(EventoLote.eventosetor_id.is_(None))
        total_existente = db.query(func.coalesce(func.sum(EventoLote.qttotallote), 0)).filter(*filtro_capacidade).scalar() or 0
        quantidade_total = data.qttotallote
        if quantidade_total is None:
            quantidade_total = max(int(capacidade) - int(total_existente), 0)
        if quantidade_total <= 0 or int(total_existente) + quantidade_total > int(capacidade):
            raise HTTPException(status_code=422, detail="A soma dos ingressos não pode ultrapassar a capacidade disponível")

        novo = EventoLote(
            organizacao_id=data.organizacao_id,
            loja_id=data.loja_id,
            evento_id=evento_id,
            eventosetor_id=data.eventosetor_id,
            nrlote=data.nrlote,
            tipoingresso=data.tipoingresso,
            nmlote=data.nmlote,
            vrprecolote=data.vrprecolote,
            qttotallote=quantidade_total,
            qtvendidalote=data.qtvendidalote,
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
    usuario: dict = Depends(get_usuario_logado),
):
    try:
        lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado")
        validar_mutacao_loja(usuario, lote.organizacao_id, lote.loja_id)

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
        if "eventosetor_id" in data.model_fields_set:
            if data.eventosetor_id is not None and not db.query(EventoSetor).filter(EventoSetor.eventosetor_id == data.eventosetor_id, EventoSetor.evento_id == lote.evento_id).first():
                raise HTTPException(status_code=404, detail="Setor do evento não encontrado")
            lote.eventosetor_id = data.eventosetor_id
        if data.nrlote is not None: lote.nrlote = data.nrlote
        if data.tipoingresso is not None: lote.tipoingresso = data.tipoingresso

        if data.vrprecolote is not None:
            lote.vrprecolote = data.vrprecolote

        if data.qttotallote is not None:
            loja_capacidade = db.query(Loja).filter(Loja.loja_id == lote.loja_id).first()
            setor_id_atual = getattr(lote, "eventosetor_id", None)
            setor_capacidade = db.query(EventoSetor).filter(EventoSetor.eventosetor_id == setor_id_atual).first() if setor_id_atual else None
            capacidade = setor_capacidade.qtcapacidade if setor_capacidade else getattr(loja_capacidade, "qtcpdloja", None)
            filtro = [EventoLote.evento_id == lote.evento_id, EventoLote.lote_id != lote_id]
            filtro.append(EventoLote.eventosetor_id == setor_id_atual if setor_id_atual else EventoLote.eventosetor_id.is_(None))
            total_outros = db.query(func.coalesce(func.sum(EventoLote.qttotallote), 0)).filter(*filtro).scalar() or 0
            if not capacidade or int(total_outros) + data.qttotallote > int(capacidade):
                raise HTTPException(status_code=422, detail="A soma dos ingressos não pode ultrapassar a capacidade disponível")
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
                "eventosetor_id": getattr(lote, "eventosetor_id", None),
                "nmsetor": getattr(lote, "nmsetor", None),
                "nrlote": getattr(lote, "nrlote", 1),
                "tipoingresso": getattr(lote, "tipoingresso", "UNICO"),
                "vrprecolote": float(lote.vrprecolote or 0),
                "qttotallote": lote.qttotallote,
                "qtvendidalote": lote.qtvendidalote,
                "dtiniciovenda": lote.dtiniciovenda,
                "dtfimvenda": lote.dtfimvenda,
                "statuslote": lote.statuslote,
                "dtcriacao": lote.dtcriacao,
                "dtultatu": lote.dtultatu,
            }
        }

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar lote: {str(e)}")


@router.delete("/lotes/{lote_id}")
def deletar_lote_evento(
    lote_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    try:
        lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()

        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado")
        validar_mutacao_loja(usuario, lote.organizacao_id, lote.loja_id)

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


@router.get("/lotes/{lote_id}/quantidade-vendida")
def quantidade_vendida_lote(
    lote_id: int,
    db: Session = Depends(get_db),
):
    lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()

    if not lote:
        raise HTTPException(status_code=404, detail="Lote não encontrado")

    qtd_vendida = (
        db.query(ItVenda)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(ItVenda.lote_id == lote_id)
        .filter(Venda.sitvenda == "PAGA")
        .count()
    )

    from app.services.reserva_ingresso_service import expirar_reservas, quantidade_reservada
    expirar_reservas(db, lote_id)
    qtd_reservada = quantidade_reservada(db, lote_id)
    if qtd_reservada:
        db.commit()
    sem_limite = lote.qttotallote is None
    qtd_total = None if sem_limite else int(lote.qttotallote)
    qtd_disponivel = None if sem_limite else max(qtd_total - qtd_vendida - qtd_reservada, 0)

    return {
        "lote_id": lote_id,
        "qt_total": qtd_total,
        "qt_vendida": qtd_vendida,
        "qt_reservada": qtd_reservada,
        "qt_disponivel": qtd_disponivel,
        "sem_limite": sem_limite,
        "esgotado": False if sem_limite else qtd_disponivel <= 0,
    }
