from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.evento import Evento
from app.models.eventoatracao import EventoAtracao
from app.models.eventolote import EventoLote
from app.models.eventoloteglobal import EventoLoteGlobal
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.models.loja import Loja
from app.models.modalidadeingresso import ModalidadeIngresso
from app.models.modalidadebeneficio import ModalidadeBeneficio
from app.models.beneficioingresso import BeneficioIngresso
from app.models.reserva_ingresso import ReservaIngresso
from app.services.taxa_service import calcular_taxa_ingresso_unitaria
from app.utils.datetime_utils import FUSO_BRASIL
from app.core.config import PERCENTUAL_COTA_LEGAL


STATUS_RESERVAM_ESTOQUE = ("PREENCHENDO", "AGUARDANDO_PAGAMENTO")
PRAZO_RESERVA_INGRESSO = timedelta(minutes=15)


def _agora_brasilia() -> datetime:
    """Datas comerciais dos lotes e dos eventos são informadas em Brasília."""
    return datetime.now(FUSO_BRASIL).replace(tzinfo=None)


def _fim_efetivo_evento(db: Session, evento: Evento) -> datetime | None:
    if evento.dtfimevento:
        return evento.dtfimevento
    fim_atracao = (
        db.query(func.max(EventoAtracao.dtfimatracao))
        .filter(EventoAtracao.evento_id == evento.evento_id)
        .scalar()
    )
    if fim_atracao:
        return fim_atracao
    if evento.dtinicioevento:
        return evento.dtinicioevento + timedelta(hours=6)
    return None


def expirar_reservas(db: Session, lote_id: int | None = None) -> int:
    query = db.query(ReservaIngresso).filter(
        ReservaIngresso.sitreserva.in_(STATUS_RESERVAM_ESTOQUE),
        ReservaIngresso.dtexpiracao <= datetime.now(),
    )
    if lote_id is not None:
        query = query.filter(ReservaIngresso.lote_id == lote_id)
    return query.update({ReservaIngresso.sitreserva: "EXPIRADA"}, synchronize_session=False)


def quantidade_reservada(db: Session, lote_id: int) -> int:
    return int(
        db.query(func.coalesce(func.sum(ReservaIngresso.qtreservada), 0))
        .filter(
            ReservaIngresso.lote_id == lote_id,
            ReservaIngresso.sitreserva.in_(STATUS_RESERVAM_ESTOQUE),
            ReservaIngresso.dtexpiracao > datetime.now(),
        )
        .scalar()
        or 0
    )


def quantidade_disponivel_configuracao(db: Session, lote: EventoLote) -> int:
    """Estoque disponível na etapa comercial, sem exceder o setor.

    Cada lote global é uma faixa de preço/tempo, não uma nova capacidade
    física. Portanto, o limite configurado no lote indica quanto aquele setor
    pode oferecer *naquela etapa*; as vendas e reservas de etapas anteriores
    continuam consumindo o mesmo estoque do setor.
    """
    setor = lote.setor
    if not setor:
        if lote.qtlimite is None:
            return 0
        return max(
            0,
            int(lote.qtlimite)
            - int(lote.qtvendidalote or 0)
            - quantidade_reservada(db, lote.lote_id),
        )
    disponivel_no_setor = capacidade_restante_setor(
        db,
        int(lote.evento_id),
        int(setor.eventosetor_id),
        int(setor.qtcapacidade),
    )
    if lote.qtlimite is None:
        return disponivel_no_setor
    disponivel_no_lote = max(
        0,
        int(lote.qtlimite)
        - int(lote.qtvendidalote or 0)
        - quantidade_reservada(db, lote.lote_id),
    )
    return min(disponivel_no_lote, disponivel_no_setor)


def capacidade_restante_setor(db: Session, evento_id: int, setor_id: int, capacidade: int) -> int:
    vendidos = int(
        db.query(func.coalesce(func.sum(EventoLote.qtvendidalote), 0))
        .filter(EventoLote.evento_id == evento_id, EventoLote.eventosetor_id == setor_id)
        .scalar()
        or 0
    )
    reservados = int(
        db.query(func.coalesce(func.sum(ReservaIngresso.qtreservada), 0))
        .join(EventoLote, EventoLote.lote_id == ReservaIngresso.lote_id)
        .filter(
            EventoLote.evento_id == evento_id,
            EventoLote.eventosetor_id == setor_id,
            ReservaIngresso.sitreserva.in_(STATUS_RESERVAM_ESTOQUE),
            ReservaIngresso.dtexpiracao > datetime.now(),
        )
        .scalar()
        or 0
    )
    return max(0, capacidade - vendidos - reservados)


def _lote_global_esgotado(db: Session, lote_global: EventoLoteGlobal) -> bool:
    configuracoes = [
        configuracao
        for configuracao in lote_global.configuracoes_setor
        if configuracao.situacao == "ATIVO" and configuracao.setor and configuracao.setor.sitsetor == "ATIVO"
    ]
    return bool(configuracoes) and all(
        quantidade_disponivel_configuracao(db, configuracao) <= 0
        for configuracao in configuracoes
    )


def lote_global_ativo(
    db: Session, evento_id: int, agora: datetime | None = None
) -> EventoLoteGlobal | None:
    """Resolve o único lote comercial vigente para todos os setores."""
    agora = agora or _agora_brasilia()
    lotes = (
        db.query(EventoLoteGlobal)
        .filter(EventoLoteGlobal.evento_id == evento_id, EventoLoteGlobal.situacao == "ATIVO")
        .order_by(EventoLoteGlobal.nrlote, EventoLoteGlobal.loteglobal_id)
        .all()
    )
    for indice, lote in enumerate(lotes):
        # Só o primeiro lote tem início próprio. Nos demais, a abertura é a
        # virada do anterior, que mantém a venda sem uma janela vazia.
        if indice == 0 and lote.dtiniciovenda and agora < lote.dtiniciovenda:
            return None
        encerrou_por_data = lote.dtfimvenda is not None and agora >= lote.dtfimvenda
        encerrou_por_estoque = _lote_global_esgotado(db, lote)
        gatilho = lote.gatilhovirada
        encerrado = (
            (gatilho == "DATA" and encerrou_por_data)
            or (gatilho == "ESGOTAMENTO" and encerrou_por_estoque)
            or (gatilho == "HIBRIDO" and (encerrou_por_data or encerrou_por_estoque))
        )
        if not encerrado:
            return lote
    return None


def lote_atual_do_setor(db: Session, lote: EventoLote, agora: datetime) -> EventoLote | None:
    if lote.situacao != "ATIVO" or not lote.lote_global or lote.lote_global.situacao != "ATIVO":
        return None
    atual = lote_global_ativo(db, lote.lote_global.evento_id, agora)
    if atual is None or atual.loteglobal_id != lote.loteglobal_id:
        return None
    if quantidade_disponivel_configuracao(db, lote) <= 0:
        return None
    return lote


def _capacidade_evento(db: Session, evento: Evento) -> int:
    if evento.qtcapacidadeevento:
        return int(evento.qtcapacidadeevento)
    return int(
        db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0))
        .filter(EventoSetor.evento_id == evento.evento_id, EventoSetor.sitsetor == "ATIVO")
        .scalar()
        or 0
    )


def criar_reserva(
    db: Session,
    *,
    cliente_id: int,
    lote_id: int,
    lotepreco_id: int,
    beneficio_id: int | None,
    tipo_beneficio: str | None,
    quantidade: int,
) -> ReservaIngresso:
    lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).with_for_update().first()
    if not lote:
        raise HTTPException(404, "Configuração de setor não encontrada")
    preco = (
        db.query(EventoLotePreco)
        .filter(
            EventoLotePreco.lotepreco_id == lotepreco_id,
            EventoLotePreco.lote_id == lote_id,
            EventoLotePreco.situacao == "ATIVO",
        )
        .first()
    )
    if not preco:
        raise HTTPException(404, "Modalidade de preço não encontrada")

    modalidade = db.query(ModalidadeIngresso).filter(
        ModalidadeIngresso.modalidade_id == preco.modalidade_id,
        ModalidadeIngresso.situacao == "ATIVO",
    ).first()
    if not modalidade:
        raise HTTPException(422, "A modalidade deste ingresso não está disponível")
    beneficio_item = None
    exige_beneficio = bool(modalidade.exigebeneficio or preco.aplicacotalegal)
    if exige_beneficio:
        beneficio_item = (
            db.query(BeneficioIngresso)
            .join(ModalidadeBeneficio, ModalidadeBeneficio.beneficio_id == BeneficioIngresso.beneficio_id)
            .filter(
                ModalidadeBeneficio.modalidade_id == modalidade.modalidade_id,
                BeneficioIngresso.beneficio_id == beneficio_id,
                BeneficioIngresso.situacao == "ATIVO",
            )
            .first()
        )
        if not beneficio_item:
            raise HTTPException(422, "Selecione um benefício válido para esta modalidade")
    beneficio = beneficio_item.cdbeneficio if beneficio_item else None

    # Reservas expiram no relógio do servidor; já os períodos de venda dos
    # lotes seguem a data/hora comercial informada pelo parceiro (Brasília).
    agora = datetime.now()
    agora_vendas = _agora_brasilia()
    expirar_reservas(db)
    if lote_atual_do_setor(db, lote, agora_vendas) is None:
        raise HTTPException(409, "Este setor não está disponível no lote global vigente")
    if quantidade > quantidade_disponivel_configuracao(db, lote):
        raise HTTPException(409, "O limite deste setor no lote vigente foi atingido")

    evento = db.query(Evento).filter(Evento.evento_id == lote.evento_id).first()
    if not evento:
        raise HTTPException(404, "Evento não encontrado")
    if (evento.statusevento or "").upper() != "ATIVO":
        raise HTTPException(409, "Este evento não está disponível para venda")
    fim_evento = _fim_efetivo_evento(db, evento)
    if fim_evento is not None and agora_vendas >= fim_evento:
        raise HTTPException(409, "Este evento já foi encerrado e não aceita novas compras")
    capacidade_evento = _capacidade_evento(db, evento)
    reservada_evento = int(
        db.query(func.coalesce(func.sum(ReservaIngresso.qtreservada), 0))
        .filter(
            ReservaIngresso.evento_id == evento.evento_id,
            ReservaIngresso.sitreserva.in_(STATUS_RESERVAM_ESTOQUE),
            ReservaIngresso.dtexpiracao > agora,
        )
        .scalar()
        or 0
    )
    vendida_evento = int(
        db.query(func.coalesce(func.sum(EventoLote.qtvendidalote), 0))
        .filter(EventoLote.evento_id == evento.evento_id)
        .scalar()
        or 0
    )
    if capacidade_evento <= 0 or vendida_evento + reservada_evento + quantidade > capacidade_evento:
        raise HTTPException(409, "A capacidade total do evento foi atingida")

    setor = (
        db.query(EventoSetor)
        .filter(EventoSetor.eventosetor_id == lote.eventosetor_id, EventoSetor.evento_id == evento.evento_id)
        .with_for_update()
        .first()
    )
    if not setor or setor.sitsetor != "ATIVO":
        raise HTTPException(409, "Setor indisponível para venda")
    if quantidade > capacidade_restante_setor(db, evento.evento_id, setor.eventosetor_id, int(setor.qtcapacidade)):
        raise HTTPException(409, "A capacidade do setor foi atingida")

    # A cota é global ao evento; a modalidade apenas informa se consome essa
    # cota. A porcentagem oficial continuará em uma regra do evento, quando
    # esta for exposta ao parceiro.
    if preco.aplicacotalegal:
        usada_cota = int(
            db.query(func.coalesce(func.sum(ReservaIngresso.qtreservada), 0))
            .join(EventoLotePreco, EventoLotePreco.lotepreco_id == ReservaIngresso.lotepreco_id)
            .filter(
                ReservaIngresso.evento_id == evento.evento_id,
                EventoLotePreco.aplicacotalegal.is_(True),
                ReservaIngresso.sitreserva.in_(("PREENCHENDO", "AGUARDANDO_PAGAMENTO", "CONFIRMADA")),
            )
            .scalar()
            or 0
        )
        if usada_cota + quantidade > int(
            capacidade_evento * PERCENTUAL_COTA_LEGAL / 100
        ):
            raise HTTPException(409, "A cota legal de meia-entrada do evento foi atingida")

    loja = db.query(Loja).filter(Loja.loja_id == lote.loja_id).first()
    percentual = Decimal(str(loja.vrtaxaing or 0)) if loja else Decimal("0")
    minimo = Decimal(str(loja.vrtaxaminimaingresso or 0)) if loja else Decimal("0")
    unitario = Decimal(str(preco.vrpreco or 0)).quantize(Decimal("0.01"))
    taxa_unitaria = calcular_taxa_ingresso_unitaria(unitario, percentual, minimo)
    reserva = ReservaIngresso(
        organizacao_id=lote.organizacao_id,
        loja_id=lote.loja_id,
        cliente_id=cliente_id,
        evento_id=evento.evento_id,
        lote_id=lote.lote_id,
        lotepreco_id=preco.lotepreco_id,
        beneficio_id=beneficio_item.beneficio_id if beneficio_item else None,
        tipobeneficio=beneficio,
        nmbeneficiosnapshot=beneficio_item.nmbeneficio if beneficio_item else None,
        qtreservada=quantidade,
        vrunitario=unitario,
        pctaxa=percentual,
        vrtaxa=taxa_unitaria,
        vrtotal=((unitario + taxa_unitaria) * quantidade).quantize(Decimal("0.01")),
        sitreserva="PREENCHENDO",
        dtexpiracao=agora + PRAZO_RESERVA_INGRESSO,
    )
    db.add(reserva)
    db.flush()
    return reserva
