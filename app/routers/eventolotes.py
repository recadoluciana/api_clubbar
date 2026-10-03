from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.permissoes_loja import validar_mutacao_loja
from app.core.config import PERCENTUAL_COTA_LEGAL
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventoloteglobal import EventoLoteGlobal
from app.models.eventolotepreco import EventoLotePreco
from app.models.modalidadeingresso import ModalidadeIngresso
from app.models.modalidadebeneficio import ModalidadeBeneficio
from app.models.beneficioingresso import BeneficioIngresso
from app.models.eventosetor import EventoSetor
from app.models.itvenda import ItVenda
from app.models.itcarrinho import ItCarrinho
from app.models.loja import Loja
from app.models.reserva_ingresso import ReservaIngresso
from app.schemas.eventolote import (
    EventoLoteGlobalCreate,
    EventoLoteGlobalUpdate,
    EventoLoteSetorIn,
    EventoLoteSetorUpdate,
)
from app.services.reserva_ingresso_service import (
    capacidade_restante_setor,
    lote_global_ativo,
    quantidade_disponivel_configuracao,
    quantidade_reservada,
)
from app.services.evento_edicao_service import validar_evento_editavel
from app.utils.datetime_utils import FUSO_BRASIL


router = APIRouter(prefix="/eventos", tags=["eventos"])
STATUS_RESERVAM_ESTOQUE = ("PREENCHENDO", "AGUARDANDO_PAGAMENTO")


def _limpar_referencias_temporarias_lote(db: Session, lote_id: int) -> None:
    """Remove somente tentativas abandonadas que não representam uma venda."""
    agora = datetime.now()
    db.query(ReservaIngresso).filter(
        ReservaIngresso.lote_id == lote_id,
        ReservaIngresso.venda_id.is_(None),
        or_(
            ReservaIngresso.dtexpiracao <= agora,
            ReservaIngresso.sitreserva.in_(("EXPIRADA", "CANCELADA")),
        ),
    ).delete(synchronize_session=False)
    db.query(ItCarrinho).filter(ItCarrinho.lote_id == lote_id).delete(
        synchronize_session=False
    )


def _validar_exclusao_configuracao_lote(db: Session, lote: EventoLote) -> None:
    tem_vendas = db.query(ItVenda.itvenda_id).filter(ItVenda.lote_id == lote.lote_id).first()
    tem_reserva_valida = (
        db.query(ReservaIngresso.reserva_ingresso_id)
        .filter(
            ReservaIngresso.lote_id == lote.lote_id,
            or_(
                ReservaIngresso.venda_id.is_not(None),
                ReservaIngresso.dtexpiracao > datetime.now(),
            ),
        )
        .first()
    )
    if tem_vendas or tem_reserva_valida:
        raise HTTPException(
            409,
            "Não é possível excluir este lote porque ele possui vendas ou reservas válidas.",
        )
    _limpar_referencias_temporarias_lote(db, lote.lote_id)


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


def _dados_preco_catalogo(db: Session, preco) -> dict:
    modalidade = db.query(ModalidadeIngresso).filter(
        ModalidadeIngresso.modalidade_id == preco.modalidade_id,
        ModalidadeIngresso.situacao == "ATIVO",
    ).first()
    if not modalidade:
        raise HTTPException(422, "Modalidade de ingresso inexistente ou inativa")
    return {
        "modalidade_id": modalidade.modalidade_id,
        "nmpreco": preco.nmpreco if modalidade.permitepersonalizarnome else modalidade.nmmodalidade,
        "tipopreco": modalidade.cdmodalidade,
        "vrpreco": preco.vrpreco,
        "aplicacotalegal": bool(modalidade.aplicacotalegal),
        "exigecomprovante": bool(modalidade.exigecomprovante),
        "situacao": preco.situacao,
        "nrordem": preco.nrordem,
    }


def _saida_configuracao(db: Session, lote: EventoLote, evento: Evento) -> dict:
    vendidos_cota, reservados_cota = _uso_cota_legal_evento(db, evento.evento_id)
    reservados = quantidade_reservada(db, lote.lote_id)
    setor = lote.setor
    global_ = lote.lote_global
    disponibilidade = quantidade_disponivel_configuracao(db, lote)
    base_cota_lote = (
        int(lote.qtlimite)
        if lote.qtlimite is not None
        else int(setor.qtcapacidade) if setor else 0
    )
    quantidade_cota_lote = int(base_cota_lote * PERCENTUAL_COTA_LEGAL / 100)
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
        "dssetor": setor.dssetor if setor else None,
        "qttotallote": int(lote.qtlimite) if lote.qtlimite is not None else None,
        "qtlimite": int(lote.qtlimite) if lote.qtlimite is not None else None,
        "usarcapacidaderestante": lote.qtlimite is None,
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
        "cotalegal": int(
            _capacidade_total_evento(db, evento)
            * PERCENTUAL_COTA_LEGAL
            / 100
        ),
        "percentualcotalegal": PERCENTUAL_COTA_LEGAL,
        "qtlimitecotalegal": quantidade_cota_lote,
        "qtvendidacotalegal": vendidos_cota,
        "qtreservadacotalegal": reservados_cota,
        "precos": [
            {
                "lotepreco_id": preco.lotepreco_id,
                "modalidade_id": preco.modalidade_id,
                "nmpreco": preco.nmpreco,
                "tipopreco": preco.tipopreco,
                "vrpreco": float(preco.vrpreco),
                "aplicacotalegal": bool(preco.aplicacotalegal),
                "exigecomprovante": bool(preco.exigecomprovante),
                "situacao": preco.situacao,
                "nrordem": int(preco.nrordem),
                "exigebeneficio": bool(preco.aplicacotalegal)
                or bool(
                    db.query(ModalidadeIngresso.exigebeneficio)
                    .filter(ModalidadeIngresso.modalidade_id == preco.modalidade_id)
                    .scalar()
                ),
                "beneficios": [
                    {
                        "beneficio_id": beneficio.beneficio_id,
                        "cdbeneficio": beneficio.cdbeneficio,
                        "nmbeneficio": beneficio.nmbeneficio,
                        "exigecomprovante": bool(beneficio.exigecomprovante),
                    }
                    for beneficio in db.query(BeneficioIngresso)
                    .join(ModalidadeBeneficio, ModalidadeBeneficio.beneficio_id == BeneficioIngresso.beneficio_id)
                    .filter(
                        ModalidadeBeneficio.modalidade_id == preco.modalidade_id,
                        BeneficioIngresso.situacao == "ATIVO",
                    )
                    .order_by(BeneficioIngresso.nrordem)
                    .all()
                ],
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
    extras = set(por_setor) - ids_ativos
    if extras:
        raise HTTPException(422, "Há setores inválidos informados neste lote global")

    # Um lote global é uma etapa única de vendas, mas nem todo setor precisa
    # participar dela. Os setores ausentes ficam indisponíveis até serem
    # incluídos em outra etapa global.
    for setor in ativos:
        dados_setor = por_setor.get(setor.eventosetor_id)
        if dados_setor is None:
            continue
        if dados_setor.qtlimite is None:
            continue
        limite_novo = int(dados_setor.qtlimite)
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
        # A configuração continua visível mesmo sem disponibilidade para que o
        # cliente veja o setor e sua situação de esgotado. O checkout segue
        # bloqueado pela quantidade disponível.
        if configuracao.situacao == "ATIVO"
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
    lote_atual = lote_global_ativo(db, evento_id)
    numero_atual = lote_atual.nrlote if lote_atual else None
    antes_do_inicio = bool(
        not lote_atual
        and globais
        and globais[0].dtiniciovenda
        and datetime.now() < globais[0].dtiniciovenda
    )
    resultado = []
    for global_ in globais:
        carregado = _carregar_global(db, global_.loteglobal_id)
        for item in carregado.configuracoes_setor:
            saida = _saida_configuracao(db, item, evento)
            if global_.situacao != "ATIVO" or item.situacao != "ATIVO":
                saida["statuslote"] = "INATIVO"
            elif numero_atual is not None and global_.nrlote < numero_atual:
                saida["statuslote"] = "ENCERRADO"
            elif numero_atual is not None and global_.nrlote > numero_atual:
                saida["statuslote"] = "AGUARDANDO"
            elif numero_atual is None:
                saida["statuslote"] = "AGUARDANDO" if antes_do_inicio else "ENCERRADO"
            resultado.append(saida)
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
    validar_evento_editavel(evento)
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
    if numero > 1 and data.dtiniciovenda is not None:
        raise HTTPException(
            422,
            "Somente o Lote 1 tem início próprio. Os demais começam automaticamente na virada do lote anterior.",
        )
    if numero > 1:
        anterior = (
            db.query(EventoLoteGlobal)
            .filter(
                EventoLoteGlobal.evento_id == evento_id,
                EventoLoteGlobal.nrlote == numero - 1,
            )
            .first()
        )
        anterior_carregado = _carregar_global(db, anterior.loteglobal_id) if anterior else None
        sem_meta = bool(
            anterior_carregado
            and anterior_carregado.configuracoes_setor
            and all(item.qtlimite is None for item in anterior_carregado.configuracoes_setor)
        )
        if anterior_carregado and anterior_carregado.dtfimvenda is None and sem_meta:
            raise HTTPException(
                422,
                "Defina uma meta ou uma data limite no lote anterior antes de criar o próximo.",
            )
    _validar_setores_do_lote(db, evento=evento, configuracoes=data.setores)

    global_ = EventoLoteGlobal(
        organizacao_id=evento.organizacao_id,
        loja_id=evento.loja_id,
        evento_id=evento_id,
        nrlote=numero,
        nmlote=(data.nmlote or f"Lote {numero}").strip(),
        dtiniciovenda=None,
        dtfimvenda=data.dtfimvenda,
        gatilhovirada="HIBRIDO",
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
        db.add_all(EventoLotePreco(lote_id=configuracao.lote_id, **_dados_preco_catalogo(db, preco)) for preco in setor_dados.precos)
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
    evento = db.query(Evento).filter(Evento.evento_id == global_.evento_id).first()
    validar_evento_editavel(evento)
    if global_.nrlote != 1 and data.dtiniciovenda is not None:
        raise HTTPException(
            422,
            "Somente o Lote 1 tem início próprio. Os demais começam automaticamente na virada do lote anterior.",
        )
    for campo in ("nmlote", "situacao"):
        valor = getattr(data, campo)
        if valor is not None:
            setattr(global_, campo, valor)
    if "dtfimvenda" in data.model_fields_set:
        global_.dtfimvenda = data.dtfimvenda
    global_.gatilhovirada = "HIBRIDO"
    if global_.dtiniciovenda and global_.dtfimvenda and global_.dtfimvenda <= global_.dtiniciovenda:
        raise HTTPException(422, "O fim das vendas deve ser posterior ao início")
    db.commit()
    return {"mensagem": "Lote global atualizado com sucesso"}


@router.post("/lotes-globais/{loteglobal_id}/setores", status_code=201)
def adicionar_setor_ao_lote_global(
    loteglobal_id: int,
    data: EventoLoteSetorIn,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    global_ = _carregar_global(db, loteglobal_id)
    if not global_:
        raise HTTPException(404, "Lote global não encontrado")
    validar_mutacao_loja(usuario, global_.organizacao_id, global_.loja_id)
    evento = db.query(Evento).filter(Evento.evento_id == global_.evento_id).first()
    validar_evento_editavel(evento)
    setor = (
        db.query(EventoSetor)
        .filter(
            EventoSetor.eventosetor_id == data.eventosetor_id,
            EventoSetor.evento_id == global_.evento_id,
            EventoSetor.sitsetor == "ATIVO",
        )
        .first()
    )
    if not setor:
        raise HTTPException(422, "O setor informado não está ativo neste evento")
    if any(item.eventosetor_id == setor.eventosetor_id for item in global_.configuracoes_setor):
        raise HTTPException(409, "Este setor já participa deste lote global")
    if data.qtlimite is not None and data.qtlimite > int(setor.qtcapacidade):
        raise HTTPException(
            422,
            f"A quantidade deste lote não pode superar a capacidade de {setor.qtcapacidade} pessoas do setor",
        )
    configuracao = EventoLote(
        loteglobal_id=global_.loteglobal_id,
        eventosetor_id=setor.eventosetor_id,
        qtlimite=data.qtlimite,
        qtvendidalote=0,
        situacao="ATIVO",
    )
    db.add(configuracao)
    db.flush()
    db.add_all(
        EventoLotePreco(lote_id=configuracao.lote_id, **_dados_preco_catalogo(db, preco))
        for preco in data.precos
    )
    db.commit()
    return {"mensagem": "Setor adicionado ao lote global com sucesso", "lote_id": configuracao.lote_id}


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
    evento = db.query(Evento).filter(Evento.evento_id == global_.evento_id).first()
    validar_evento_editavel(evento)
    if "qtlimite" in data.model_fields_set:
        setor = lote.setor
        if data.qtlimite is not None and data.qtlimite > int(setor.qtcapacidade):
            raise HTTPException(422, "A quantidade deste lote não pode ultrapassar a capacidade do setor")
        if data.qtlimite is not None and data.qtlimite < int(lote.qtvendidalote or 0) + quantidade_reservada(db, lote.lote_id):
            raise HTTPException(422, "O limite não pode ficar abaixo das vendas e reservas existentes")
        lote.qtlimite = data.qtlimite
    if data.situacao is not None:
        lote.situacao = data.situacao
    if data.precos is not None:
        if int(lote.qtvendidalote or 0) or quantidade_reservada(db, lote.lote_id):
            raise HTTPException(409, "Não altere modalidades com vendas ou reservas. Configure o próximo lote.")
        db.query(EventoLotePreco).filter(EventoLotePreco.lote_id == lote_id).delete()
        db.add_all(EventoLotePreco(lote_id=lote_id, **_dados_preco_catalogo(db, preco)) for preco in data.precos)
    db.commit()
    return {"mensagem": "Setor do lote atualizado com sucesso"}


@router.delete("/lotes/{lote_id}")
def excluir_setor_do_lote(
    lote_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()
    if not lote:
        raise HTTPException(404, "Setor do lote não encontrado")
    global_ = _carregar_global(db, lote.loteglobal_id)
    validar_mutacao_loja(usuario, global_.organizacao_id, global_.loja_id)
    evento = db.query(Evento).filter(Evento.evento_id == global_.evento_id).first()
    validar_evento_editavel(evento)
    if len(global_.configuracoes_setor) <= 1:
        raise HTTPException(409, "Este é o único setor do lote. Exclua o lote global inteiro.")
    _validar_exclusao_configuracao_lote(db, lote)
    db.delete(lote)
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(
            409,
            "Não é possível excluir este setor porque ele possui histórico vinculado.",
        ) from erro
    return {"mensagem": "Setor removido do lote global com sucesso"}


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
    evento = db.query(Evento).filter(Evento.evento_id == global_.evento_id).first()
    validar_evento_editavel(evento)
    quantidade_lotes = (
        db.query(func.count(EventoLoteGlobal.loteglobal_id))
        .filter(EventoLoteGlobal.evento_id == global_.evento_id)
        .scalar()
        or 0
    )
    if evento.statusevento == "ATIVO" and int(quantidade_lotes) <= 1:
        raise HTTPException(
            409,
            "Não é possível excluir o último lote global de um evento publicado. "
            "Retire a publicação do evento antes de excluir este lote.",
        )
    for item in global_.configuracoes_setor:
        _validar_exclusao_configuracao_lote(db, item)
    db.delete(global_)
    try:
        db.commit()
    except IntegrityError as erro:
        db.rollback()
        raise HTTPException(
            409,
            "Não é possível excluir este lote porque ele possui histórico vinculado.",
        ) from erro
    return {"mensagem": "Lote global excluído com sucesso"}


@router.post("/lotes-globais/{loteglobal_id}/avancar")
def avancar_lote_global(
    loteglobal_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    global_ = _carregar_global(db, loteglobal_id)
    if not global_:
        raise HTTPException(404, "Lote global não encontrado")
    validar_mutacao_loja(usuario, global_.organizacao_id, global_.loja_id)
    evento = db.query(Evento).filter(Evento.evento_id == global_.evento_id).first()
    validar_evento_editavel(evento)
    atual = lote_global_ativo(db, global_.evento_id)
    if not atual or atual.loteglobal_id != global_.loteglobal_id:
        raise HTTPException(409, "Somente o lote atualmente em venda pode ser encerrado")
    proximo = (
        db.query(EventoLoteGlobal)
        .filter(
            EventoLoteGlobal.evento_id == global_.evento_id,
            EventoLoteGlobal.situacao == "ATIVO",
            EventoLoteGlobal.nrlote > global_.nrlote,
        )
        .order_by(EventoLoteGlobal.nrlote)
        .first()
    )
    if not proximo:
        raise HTTPException(409, "Cadastre o próximo lote antes de encerrar o atual")
    global_.dtfimvenda = datetime.now(FUSO_BRASIL).replace(tzinfo=None)
    db.commit()
    return {"mensagem": f"{proximo.nmlote} iniciado com sucesso"}


@router.get("/lotes/{lote_id}/quantidade-vendida")
def quantidade_vendida_lote(lote_id: int, db: Session = Depends(get_db)):
    lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()
    if not lote:
        raise HTTPException(404, "Configuração do setor não encontrada")
    reservada = quantidade_reservada(db, lote_id)
    return {
        "lote_id": lote_id,
        "qt_total": int(lote.qtlimite) if lote.qtlimite is not None else None,
        "qt_vendida": int(lote.qtvendidalote or 0),
        "qt_reservada": reservada,
        "qt_disponivel": quantidade_disponivel_configuracao(db, lote),
        "sem_limite": lote.qtlimite is None,
        "esgotado": quantidade_disponivel_configuracao(db, lote) <= 0,
    }
