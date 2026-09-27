from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventoloteglobal import EventoLoteGlobal
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.reserva_ingresso import ReservaIngresso
from app.schemas.eventolote import (
    EventoLoteGlobalCreate,
    EventoLoteGlobalUpdate,
    EventoLoteSetorUpdate,
)
from app.services.reserva_ingresso_service import (
    capacidade_restante_setor,
    lote_global_ativo,
    quantidade_disponivel_configuracao,
    quantidade_reservada,
)


router = APIRouter(prefix="/eventos", tags=["eventos"])
STATUS_RESERVAM_ESTOQUE = ("PREENCHENDO", "AGUARDANDO_PAGAMENTO")


def _capacidade_total_evento(db: Session, evento: Evento) -> int:
    if evento.qtcapacidadeevento:
        return int(evento.qtcapacidadeevento)
    return int(
        db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0))
        .filter(EventoSetor.evento_id == evento.evento_id, EventoSetor.sitsetor == "ATIVO")
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
            ReservaIngresso.sitreserva.in_(STATUS_RESERVAM_ESTOQUE),
            ReservaIngresso.dtexpiracao > datetime.now(),
            EventoLotePreco.aplicacotalegal.is_(True),
        )
        .scalar()
        or 0
    )
    return vendidos, reservados


def _carregar_global(db: Session, loteglobal_id: int) -> EventoLoteGlobal | None:
    return (
        db.query(EventoLoteGlobal)
        .options(
            joinedload(EventoLoteGlobal.configuracoes_setor).joinedload(EventoLote.setor),
            joinedload(EventoLoteGlobal.configuracoes_setor).joinedload(EventoLote.precos),
        )
        .filter(EventoLoteGlobal.loteglobal_id == loteglobal_id)
        .first()
    )


def _saida_configuracao(db: Session, lote: EventoLote, evento: Evento) -> dict:
    vendidos_cota, reservados_cota = _uso_cota_legal_evento(db, evento.evento_id)
    reservados = quantidade_reservada(db, lote.lote_id)
    setor = lote.setor
    global_ = lote.lote_global
    disponibilidade = quantidade_disponivel_configuracao(db, lote)
    return {
        "lote_id": lote.lote_id,
        "loteglobal_id": global_.loteglobal_id,
        "organizacao_id": global_.organizacao_id,
        "loja_id": global_.loja_id,
        "evento_id": global_.evento_id,
        "nmlote": global_.nmlote,
        "nrlote": global_.nrlote,
        "eventosetor_id": lote.eventosetor_id,
        "nmsetor": setor.nmsetor if setor else None,
        "qttotallote": int(lote.qtlimite),
        "qtlimite": int(lote.qtlimite),
        "qtvendidalote": int(lote.qtvendidalote or 0),
        "qtreservadalote": reservados,
        "qtdisponivel": disponibilidade,
        "qtcapacidade_setor": int(setor.qtcapacidade) if setor else None,
        "qtcapacidaderestante": (
            capacidade_restante_setor(db, evento.evento_id, setor.eventosetor_id, int(setor.qtcapacidade))
            if setor else None
        ),
        "dtiniciovenda": global_.dtiniciovenda,
        "dtfimvenda": global_.dtfimvenda,
        "gatilhovirada": global_.gatilhovirada,
        "statuslote": global_.situacao if lote.situacao == "ATIVO" else "INATIVO",
        "cotalegal": int(_capacidade_total_evento(db, evento) * 0.40),
        "qtvendidacotalegal": vendidos_cota,
        "qtreservadacotalegal": reservados_cota,
        "precos": [
            {
                "lotepreco_id": preco.lotepreco_id,
                "nmpreco": preco.nmpreco,
                "tipopreco": preco.tipopreco,
                "vrpreco": float(preco.vrpreco),
                "aplicacotalegal": bool(preco.aplicacotalegal),
                "exigecomprovante": bool(preco.exigecomprovante),
                "situacao": preco.situacao,
                "nrordem": int(preco.nrordem),
            }
            for preco in lote.precos
        ],
    }


def _saida_global(db: Session, global_: EventoLoteGlobal, evento: Evento) -> dict:
    configuracoes = sorted(
        global_.configuracoes_setor,
        key=lambda item: ((item.setor.nrordem if item.setor else 999999), item.lote_id),
    )
    return {
        "loteglobal_id": global_.loteglobal_id,
        "evento_id": global_.evento_id,
        "organizacao_id": global_.organizacao_id,
        "loja_id": global_.loja_id,
        "nrlote": global_.nrlote,
        "nmlote": global_.nmlote,
        "dtiniciovenda": global_.dtiniciovenda,
        "dtfimvenda": global_.dtfimvenda,
        "gatilhovirada": global_.gatilhovirada,
        "situacao": global_.situacao,
        "disponivel_globalmente": lote_global_ativo(db, evento.evento_id) == global_,
        "setores": [_saida_configuracao(db, item, evento) for item in configuracoes],
    }


def _validar_setores_do_lote(
    db: Session,
    *,
    evento: Evento,
    configuracoes: list,
    ignorar_loteglobal_id: int | None = None,
) -> None:
    ativos = (
        db.query(EventoSetor)
        .filter(EventoSetor.evento_id == evento.evento_id, EventoSetor.sitsetor == "ATIVO")
        .all()
    )
    ids_ativos = {setor.eventosetor_id for setor in ativos}
    por_setor = {item.eventosetor_id: item for item in configuracoes}
    if len(por_setor) != len(configuracoes):
        raise HTTPException(422, "Cada setor pode ser configurado apenas uma vez no lote global")
    if set(por_setor) != ids_ativos:
        faltantes = [setor.nmsetor for setor in ativos if setor.eventosetor_id not in por_setor]
        extras = set(por_setor) - ids_ativos
        detalhe = []
        if faltantes:
            detalhe.append("faltam: " + ", ".join(faltantes))
        if extras:
            detalhe.append("setores inválidos informados")
        raise HTTPException(422, "Todo lote global deve configurar todos os setores ativos (" + "; ".join(detalhe) + ")")

    for setor in ativos:
        limite_novo = int(por_setor[setor.eventosetor_id].qtlimite)
        # Lotes globais são etapas sequenciais de preço. A quantidade de uma
        # etapa não é somada à das anteriores; todos compartilham o estoque do
        # setor e as vendas anteriores são descontadas no checkout.
        if limite_novo > int(setor.qtcapacidade):
            raise HTTPException(
                422,
                f"A quantidade de {setor.nmsetor} neste lote não pode superar a capacidade de {setor.qtcapacidade} pessoas",
            )


@router.get("/{evento_id}/lotes")
def listar_lotes_disponiveis(evento_id: int, db: Session = Depends(get_db)):
    evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()
    if not evento:
        raise HTTPException(404, "Evento não encontrado")
    atual = lote_global_ativo(db, evento_id)
    if not atual:
        return []
    global_ = _carregar_global(db, atual.loteglobal_id)
    return [
        _saida_configuracao(db, configuracao, evento)
        for configuracao in global_.configuracoes_setor
        if configuracao.situacao == "ATIVO" and quantidade_disponivel_configuracao(db, configuracao) > 0
    ]


@router.get("/{evento_id}/lotes_todos")
def listar_todos_lotes_evento(evento_id: int, db: Session = Depends(get_db)):
    evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()
    if not evento:
        raise HTTPException(404, "Evento não encontrado")
    globais = (
        db.query(EventoLoteGlobal)
        .filter(EventoLoteGlobal.evento_id == evento_id)
        .order_by(EventoLoteGlobal.nrlote)
        .all()
    )
    resultado = []
    for global_ in globais:
        carregado = _carregar_global(db, global_.loteglobal_id)
        resultado.extend(_saida_configuracao(db, item, evento) for item in carregado.configuracoes_setor)
    return resultado


@router.get("/{evento_id}/lotes-globais")
def listar_lotes_globais(evento_id: int, db: Session = Depends(get_db)):
    evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()
    if not evento:
        raise HTTPException(404, "Evento não encontrado")
    globais = (
        db.query(EventoLoteGlobal)
        .filter(EventoLoteGlobal.evento_id == evento_id)
        .order_by(EventoLoteGlobal.nrlote)
        .all()
    )
    return [_saida_global(db, _carregar_global(db, item.loteglobal_id), evento) for item in globais]


@router.post("/{evento_id}/lotes", status_code=201)
def criar_lote_global(
    evento_id: int,
    data: EventoLoteGlobalCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()
    if not evento:
        raise HTTPException(404, "Evento não encontrado")
    validar_mutacao_loja(usuario, evento.organizacao_id, evento.loja_id)
    loja = db.query(Loja).filter(Loja.loja_id == data.loja_id).first()
    if not loja or data.organizacao_id != evento.organizacao_id or data.loja_id != evento.loja_id:
        raise HTTPException(422, "Organização ou loja divergente do evento")

    proximo_numero = int(
        db.query(func.coalesce(func.max(EventoLoteGlobal.nrlote), 0))
        .filter(EventoLoteGlobal.evento_id == evento_id)
        .scalar()
        or 0
    ) + 1
    numero = data.nrlote or proximo_numero
    if numero != proximo_numero:
        raise HTTPException(422, f"O próximo lote global deve ser o Lote {proximo_numero}")
    if numero == 1 and data.dtiniciovenda is None:
        raise HTTPException(422, "Informe o início das vendas do Lote 1")
    if numero > 1 and data.dtiniciovenda is not None:
        raise HTTPException(
            422,
            "Somente o Lote 1 tem início próprio. Os demais começam automaticamente na virada do lote anterior.",
        )
    if data.gatilhovirada in {"DATA", "HIBRIDO"} and data.dtfimvenda is None:
        raise HTTPException(422, "Informe o fim das vendas para a virada programada")
    _validar_setores_do_lote(db, evento=evento, configuracoes=data.setores)

    global_ = EventoLoteGlobal(
        organizacao_id=evento.organizacao_id,
        loja_id=evento.loja_id,
        evento_id=evento_id,
        nrlote=numero,
        nmlote=(data.nmlote or f"Lote {numero}").strip(),
        dtiniciovenda=data.dtiniciovenda if numero == 1 else None,
        dtfimvenda=data.dtfimvenda,
        gatilhovirada=data.gatilhovirada,
        situacao="ATIVO",
    )
    db.add(global_)
    db.flush()
    for setor_dados in data.setores:
        configuracao = EventoLote(
            loteglobal_id=global_.loteglobal_id,
            eventosetor_id=setor_dados.eventosetor_id,
            qtlimite=setor_dados.qtlimite,
            qtvendidalote=0,
            situacao="ATIVO",
        )
        db.add(configuracao)
        db.flush()
        db.add_all(EventoLotePreco(lote_id=configuracao.lote_id, **preco.model_dump()) for preco in setor_dados.precos)
    db.commit()
    return {"mensagem": "Lote global cadastrado com sucesso", "loteglobal_id": global_.loteglobal_id}


@router.put("/lotes-globais/{loteglobal_id}")
def atualizar_lote_global(
    loteglobal_id: int,
    data: EventoLoteGlobalUpdate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    global_ = _carregar_global(db, loteglobal_id)
    if not global_:
        raise HTTPException(404, "Lote global não encontrado")
    validar_mutacao_loja(usuario, global_.organizacao_id, global_.loja_id)
    if global_.nrlote != 1 and data.dtiniciovenda is not None:
        raise HTTPException(
            422,
            "Somente o Lote 1 tem início próprio. Os demais começam automaticamente na virada do lote anterior.",
        )
    for campo in ("nmlote", "dtfimvenda", "gatilhovirada", "situacao"):
        valor = getattr(data, campo)
        if valor is not None:
            setattr(global_, campo, valor)
    if global_.nrlote == 1 and data.dtiniciovenda is not None:
        global_.dtiniciovenda = data.dtiniciovenda
    if global_.dtiniciovenda and global_.dtfimvenda and global_.dtfimvenda <= global_.dtiniciovenda:
        raise HTTPException(422, "O fim das vendas deve ser posterior ao início")
    db.commit()
    return {"mensagem": "Lote global atualizado com sucesso"}


@router.put("/lotes/{lote_id}")
def atualizar_configuracao_setor(
    lote_id: int,
    data: EventoLoteSetorUpdate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()
    if not lote:
        raise HTTPException(404, "Configuração do setor não encontrada")
    global_ = _carregar_global(db, lote.loteglobal_id)
    validar_mutacao_loja(usuario, global_.organizacao_id, global_.loja_id)
    if data.qtlimite is not None:
        setor = lote.setor
        if data.qtlimite > int(setor.qtcapacidade):
            raise HTTPException(422, "A quantidade deste lote não pode ultrapassar a capacidade do setor")
        if data.qtlimite < int(lote.qtvendidalote or 0) + quantidade_reservada(db, lote.lote_id):
            raise HTTPException(422, "O limite não pode ficar abaixo das vendas e reservas existentes")
        lote.qtlimite = data.qtlimite
    if data.situacao is not None:
        lote.situacao = data.situacao
    if data.precos is not None:
        if int(lote.qtvendidalote or 0) or quantidade_reservada(db, lote.lote_id):
            raise HTTPException(409, "Não altere modalidades com vendas ou reservas. Configure o próximo lote.")
        db.query(EventoLotePreco).filter(EventoLotePreco.lote_id == lote_id).delete()
        db.add_all(EventoLotePreco(lote_id=lote_id, **preco.model_dump()) for preco in data.precos)
    db.commit()
    return {"mensagem": "Setor do lote atualizado com sucesso"}


@router.delete("/lotes-globais/{loteglobal_id}")
def excluir_lote_global(
    loteglobal_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    global_ = _carregar_global(db, loteglobal_id)
    if not global_:
        raise HTTPException(404, "Lote global não encontrado")
    validar_mutacao_loja(usuario, global_.organizacao_id, global_.loja_id)
    if any(item.qtvendidalote or quantidade_reservada(db, item.lote_id) for item in global_.configuracoes_setor):
        raise HTTPException(409, "Não é possível excluir um lote global com vendas ou reservas")
    db.delete(global_)
    db.commit()
    return {"mensagem": "Lote global excluído com sucesso"}


@router.get("/lotes/{lote_id}/quantidade-vendida")
def quantidade_vendida_lote(lote_id: int, db: Session = Depends(get_db)):
    lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()
    if not lote:
        raise HTTPException(404, "Configuração do setor não encontrada")
    reservada = quantidade_reservada(db, lote_id)
    return {
        "lote_id": lote_id,
        "qt_total": int(lote.qtlimite),
        "qt_vendida": int(lote.qtvendidalote or 0),
        "qt_reservada": reservada,
        "qt_disponivel": quantidade_disponivel_configuracao(db, lote),
        "sem_limite": False,
        "esgotado": quantidade_disponivel_configuracao(db, lote) <= 0,
    }
