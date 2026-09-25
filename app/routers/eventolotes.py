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
from app.models.reserva_ingresso import ReservaIngresso
from app.services.reserva_ingresso_service import capacidade_restante_setor, quantidade_reservada

router = APIRouter(prefix="/eventos", tags=["eventos"])

def _capacidade_total_evento(db: Session, evento_id: int) -> int:
    return int(
        db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0))
        .filter(EventoSetor.evento_id == evento_id, EventoSetor.sitsetor == "ATIVO")
        .scalar()
        or 0
    )


def _uso_cota_legal_evento(db: Session, evento_id: int) -> tuple[int, int]:
    vendidos = int(
        db.query(func.coalesce(func.sum(ItVenda.qtitvenda), 0))
        .join(EventoLotePreco, EventoLotePreco.lotepreco_id == ItVenda.lotepreco_id)
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .filter(
            EventoLote.evento_id == evento_id,
            ItVenda.sititvenda == "ATIVO",
            EventoLotePreco.aplicacotalegal.is_(True),
        )
        .scalar()
        or 0
    )
    reservados = int(
        db.query(func.coalesce(func.sum(ReservaIngresso.qtreservada), 0))
        .join(EventoLotePreco, EventoLotePreco.lotepreco_id == ReservaIngresso.lotepreco_id)
        .filter(
            ReservaIngresso.evento_id == evento_id,
            EventoLotePreco.aplicacotalegal.is_(True),
            ReservaIngresso.sitreserva.in_(("PREENCHENDO", "AGUARDANDO_PAGAMENTO")),
            ReservaIngresso.dtexpiracao > datetime.now(),
        )
        .scalar()
        or 0
    )
    return vendidos, reservados


def _validar_configuracao_setor(
    db: Session,
    *,
    evento_id: int,
    setor: EventoSetor,
    nrlote: int,
    qttotallote: int | None,
    usarcapacidaderestante: bool,
    ignorar_lote_id: int | None = None,
) -> None:
    """Mantém a programação comercial coerente dentro de cada setor."""
    lotes = db.query(EventoLote).filter(
        EventoLote.evento_id == evento_id,
        EventoLote.eventosetor_id == setor.eventosetor_id,
    ).all()
    outros = [item for item in lotes if item.lote_id != ignorar_lote_id]

    if any(item.nrlote == nrlote for item in outros):
        raise HTTPException(409, "Já existe este número de lote no setor")

    restante_existente = next(
        (item for item in outros if item.usarcapacidaderestante == "S"), None
    )
    if usarcapacidaderestante:
        if restante_existente:
            raise HTTPException(409, "Já existe um lote configurado para usar a capacidade restante neste setor")
        if any(item.nrlote > nrlote for item in outros):
            raise HTTPException(422, "O lote de capacidade restante deve ser o último do setor")
    elif restante_existente:
        raise HTTPException(409, "O lote de capacidade restante deve ser sempre o último")

    if not usarcapacidaderestante:
        if qttotallote is None:
            raise HTTPException(422, "Informe o limite comercial do lote")
        total_fixo = sum(int(item.qttotallote or 0) for item in outros if item.usarcapacidaderestante != "S")
        if total_fixo + qttotallote > int(setor.qtcapacidade):
            raise HTTPException(
                422,
                "A soma dos lotes deste setor não pode ultrapassar sua capacidade",
            )


def _saida_lote(db: Session, lote: EventoLote) -> dict:
    vendidos_cota, reservados_cota = _uso_cota_legal_evento(db, lote.evento_id)
    reservas_ativas = (
        ReservaIngresso.sitreserva.in_(("PREENCHENDO", "AGUARDANDO_PAGAMENTO")),
        ReservaIngresso.dtexpiracao > datetime.now(),
    )
    reservados_lote = int(db.query(func.coalesce(func.sum(ReservaIngresso.qtreservada), 0)).filter(ReservaIngresso.lote_id == lote.lote_id, *reservas_ativas).scalar() or 0)
    capacidade_setor = int(lote.setor.qtcapacidade) if lote.setor else None
    capacidade_restante = None
    if lote.usarcapacidaderestante == "S" and capacidade_setor is not None:
        capacidade_restante = capacidade_restante_setor(db, lote.evento_id, lote.eventosetor_id, capacidade_setor)
    return {"lote_id": lote.lote_id, "organizacao_id": lote.organizacao_id, "loja_id": lote.loja_id, "evento_id": lote.evento_id, "nmlote": lote.nmlote, "eventosetor_id": lote.eventosetor_id, "nmsetor": lote.nmsetor, "nrlote": lote.nrlote, "qttotallote": lote.qttotallote, "usarcapacidaderestante": lote.usarcapacidaderestante == "S", "qtvendidalote": lote.qtvendidalote or 0, "qtreservadalote": reservados_lote, "qtcapacidade_setor": capacidade_setor, "qtcapacidaderestante": capacidade_restante, "dtiniciovenda": lote.dtiniciovenda, "dtfimvenda": lote.dtfimvenda, "statuslote": lote.statuslote, "dtcriacao": lote.dtcriacao, "dtultatu": lote.dtultatu, "cotalegal": int(_capacidade_total_evento(db, lote.evento_id) * .40), "qtvendidacotalegal": vendidos_cota, "qtreservadacotalegal": reservados_cota, "precos": [{"lotepreco_id": p.lotepreco_id, "nmpreco": p.nmpreco, "tipopreco": p.tipopreco, "vrpreco": float(p.vrpreco), "aplicacotalegal": bool(p.aplicacotalegal), "exigecomprovante": bool(p.exigecomprovante), "situacao": p.situacao, "nrordem": p.nrordem} for p in lote.precos]}


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
        if not setor:
            raise HTTPException(422, "Selecione o setor do lote")
        _validar_configuracao_setor(
            db,
            evento_id=evento_id,
            setor=setor,
            nrlote=data.nrlote,
            qttotallote=data.qttotallote,
            usarcapacidaderestante=data.usarcapacidaderestante,
        )

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

        # Valida a configuração final antes de alterá-la. Isso impede que uma
        # edição crie números repetidos, dois lotes de capacidade restante ou
        # uma soma de lotes acima da lotação do setor.
        alterou_programacao = bool(
            {"eventosetor_id", "nrlote", "qttotallote", "usarcapacidaderestante"}
            & data.model_fields_set
        )
        novo_setor_id = (
            data.eventosetor_id
            if "eventosetor_id" in data.model_fields_set
            else lote.eventosetor_id
        )
        novo_setor = None
        if alterou_programacao:
            if novo_setor_id is None:
                if lote.eventosetor_id is not None:
                    raise HTTPException(422, "Selecione o setor do lote")
            else:
                novo_setor = db.query(EventoSetor).filter(
                    EventoSetor.eventosetor_id == novo_setor_id,
                    EventoSetor.evento_id == lote.evento_id,
                ).first()
                if not novo_setor:
                    raise HTTPException(status_code=404, detail="Setor do evento não encontrado")
                if (
                    novo_setor_id != lote.eventosetor_id
                    and (int(lote.qtvendidalote or 0) > 0 or quantidade_reservada(db, lote_id) > 0)
                ):
                    raise HTTPException(409, "Não é possível mover para outro setor um lote com vendas ou reservas")
                novo_resto = (
                    data.usarcapacidaderestante
                    if data.usarcapacidaderestante is not None
                    else lote.usarcapacidaderestante == "S"
                )
                novo_total = None if novo_resto else (
                    data.qttotallote if data.qttotallote is not None else lote.qttotallote
                )
                if novo_total is not None and novo_total < int(lote.qtvendidalote or 0) + quantidade_reservada(db, lote_id):
                    raise HTTPException(422, "A capacidade não pode ser menor que as vendas e reservas atuais")
                _validar_configuracao_setor(
                    db,
                    evento_id=lote.evento_id,
                    setor=novo_setor,
                    nrlote=data.nrlote if data.nrlote is not None else lote.nrlote,
                    qttotallote=novo_total,
                    usarcapacidaderestante=novo_resto,
                    ignorar_lote_id=lote_id,
                )

        if data.nmlote is not None:
            lote.nmlote = data.nmlote
        if "eventosetor_id" in data.model_fields_set:
            lote.eventosetor_id = data.eventosetor_id
        if data.nrlote is not None: lote.nrlote = data.nrlote

        if data.qttotallote is not None:
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
