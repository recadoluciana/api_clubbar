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
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.schemas.eventolote import EventoLoteCreate, EventoLoteUpdate, EventoLoteOut
from app.models.venda import Venda
from app.models.itvenda import ItVenda

router = APIRouter(prefix="/eventos", tags=["eventos"])

def _saida_lote(db: Session, lote: EventoLote) -> dict:
    vendidos_cota = db.query(func.coalesce(func.sum(ItVenda.qtitvenda), 0)).join(EventoLotePreco, EventoLotePreco.lotepreco_id == ItVenda.lotepreco_id).filter(ItVenda.lote_id == lote.lote_id, ItVenda.sititvenda == "ATIVO", EventoLotePreco.aplicacotalegal.is_(True)).scalar() or 0
    return {"lote_id": lote.lote_id, "organizacao_id": lote.organizacao_id, "loja_id": lote.loja_id, "evento_id": lote.evento_id, "nmlote": lote.nmlote, "eventosetor_id": lote.eventosetor_id, "nmsetor": lote.nmsetor, "nrlote": lote.nrlote, "qttotallote": lote.qttotallote, "usarcapacidaderestante": lote.usarcapacidaderestante == "S", "qtvendidalote": lote.qtvendidalote or 0, "dtiniciovenda": lote.dtiniciovenda, "dtfimvenda": lote.dtfimvenda, "statuslote": lote.statuslote, "dtcriacao": lote.dtcriacao, "dtultatu": lote.dtultatu, "cotalegal": int((lote.setor.qtcapacidade if lote.setor else 0) * .40), "qtvendidacotalegal": int(vendidos_cota), "precos": [{"lotepreco_id": p.lotepreco_id, "nmpreco": p.nmpreco, "tipopreco": p.tipopreco, "vrpreco": float(p.vrpreco), "aplicacotalegal": bool(p.aplicacotalegal), "exigecomprovante": bool(p.exigecomprovante), "situacao": p.situacao, "nrordem": p.nrordem} for p in lote.precos]}


@router.get("/{evento_id}/lotes")
def listar_lotes_evento(
    evento_id: int,
    db: Session = Depends(get_db),
):

    lotes = (
        db.query(EventoLote)
        .filter(EventoLote.evento_id == evento_id)
        .filter(EventoLote.statuslote == "ATIVO")
        .outerjoin(EventoSetor, EventoSetor.eventosetor_id == EventoLote.eventosetor_id)
        .order_by(EventoLote.nrlote.asc(), EventoSetor.nrordem.asc())
        .all()
    )

    from app.services.reserva_ingresso_service import lote_atual_do_setor, expirar_reservas
    expirar_reservas(db)
    atuais = [lote for lote in lotes if lote_atual_do_setor(db, lote, datetime.now()) is lote]
    return [_saida_lote(db, lote) for lote in atuais]


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
        .order_by(EventoLote.nrlote.asc(), EventoSetor.nrordem.asc())
        .all()
    )

    return [_saida_lote(db, lote) for lote in lotes]


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
        if data.qttotallote is not None and data.qttotallote > setor.qtcapacidade:
            raise HTTPException(422, "A capacidade do lote não pode ultrapassar a capacidade do setor")
        if data.usarcapacidaderestante and db.query(EventoLote).filter(EventoLote.evento_id == evento_id, EventoLote.eventosetor_id == setor.eventosetor_id, EventoLote.usarcapacidaderestante == "S").first():
            raise HTTPException(409, "Já existe um lote configurado para usar a capacidade restante neste setor")
        ultimo_restante = db.query(EventoLote).filter(EventoLote.evento_id == evento_id, EventoLote.eventosetor_id == setor.eventosetor_id, EventoLote.usarcapacidaderestante == "S").first()
        if ultimo_restante:
            raise HTTPException(409, "O lote de capacidade restante deve ser sempre o último")
        if db.query(EventoLote).filter(EventoLote.evento_id == evento_id, EventoLote.eventosetor_id == setor.eventosetor_id, EventoLote.nrlote == data.nrlote).first():
            raise HTTPException(409, "Já existe este número de lote no setor")

        novo = EventoLote(
            organizacao_id=data.organizacao_id,
            loja_id=data.loja_id,
            evento_id=evento_id,
            eventosetor_id=data.eventosetor_id,
            nrlote=data.nrlote,
            nmlote=data.nmlote,
            qttotallote=data.qttotallote,
            usarcapacidaderestante="S" if data.usarcapacidaderestante else "N",
            qtvendidalote=0,
            dtiniciovenda=data.dtiniciovenda,
            dtfimvenda=data.dtfimvenda,
            statuslote=data.statuslote if data.statuslote else "ATIVO",
        )

        db.add(novo)
        db.flush()
        db.add_all([EventoLotePreco(lote_id=novo.lote_id, **p.model_dump()) for p in data.precos])
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

        if data.nmlote is not None:
            lote.nmlote = data.nmlote
        if "eventosetor_id" in data.model_fields_set:
            if data.eventosetor_id is not None and not db.query(EventoSetor).filter(EventoSetor.eventosetor_id == data.eventosetor_id, EventoSetor.evento_id == lote.evento_id).first():
                raise HTTPException(status_code=404, detail="Setor do evento não encontrado")
            lote.eventosetor_id = data.eventosetor_id
        if data.nrlote is not None: lote.nrlote = data.nrlote

        if data.qttotallote is not None:
            setor_id_atual = getattr(lote, "eventosetor_id", None)
            setor_capacidade = db.query(EventoSetor).filter(EventoSetor.eventosetor_id == setor_id_atual).first() if setor_id_atual else None
            if not setor_capacidade or data.qttotallote > setor_capacidade.qtcapacidade or data.qttotallote < int(lote.qtvendidalote or 0):
                raise HTTPException(422, "Capacidade inválida para o setor ou menor que a quantidade já vendida")
            lote.qttotallote = data.qttotallote
        if data.usarcapacidaderestante is not None:
            lote.usarcapacidaderestante = "S" if data.usarcapacidaderestante else "N"
            if data.usarcapacidaderestante: lote.qttotallote = None
        if data.precos is not None:
            if int(lote.qtvendidalote or 0) > 0:
                raise HTTPException(409, "Os preços de um lote com vendas não podem ser substituídos. Crie um novo lote.")
            db.query(EventoLotePreco).filter(EventoLotePreco.lote_id == lote_id).delete()
            db.add_all([EventoLotePreco(lote_id=lote_id, **p.model_dump()) for p in data.precos])

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
        db.query(func.coalesce(func.sum(ItVenda.qtitvenda), 0))
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(ItVenda.lote_id == lote_id)
        .filter(Venda.sitvenda == "PAGA")
        .scalar() or 0
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
