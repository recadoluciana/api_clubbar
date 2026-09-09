from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.eventolote import EventoLote
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.models.loja import Loja
from app.models.reserva_ingresso import ReservaIngresso
from app.services.taxa_service import calcular_taxa_ingresso_unitaria


STATUS_RESERVAM_ESTOQUE = ("PREENCHENDO", "AGUARDANDO_PAGAMENTO")

def lote_atual_do_setor(db: Session, lote: EventoLote, agora: datetime) -> EventoLote | None:
    lotes = db.query(EventoLote).filter(EventoLote.evento_id == lote.evento_id, EventoLote.eventosetor_id == lote.eventosetor_id, EventoLote.statuslote.in_(("ATIVO", "ESGOTADO", "ENCERRADO"))).order_by(EventoLote.nrlote, EventoLote.lote_id).all()
    if not lotes: return None
    iniciados = [i for i, item in enumerate(lotes) if item.dtiniciovenda is None or item.dtiniciovenda <= agora]
    indice = max(iniciados) if iniciados else 0
    for i, item in enumerate(lotes):
        reservada = quantidade_reservada(db, item.lote_id)
        esgotado = item.qttotallote is not None and int(item.qtvendidalote or 0) + reservada >= int(item.qttotallote)
        encerrado = item.dtfimvenda is not None and agora > item.dtfimvenda
        if i < indice or esgotado or encerrado:
            continue
        return item
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


BENEFICIOS_COTA = {"ESTUDANTE", "JOVEM_BAIXA_RENDA", "PCD", "ACOMPANHANTE_PCD"}

def criar_reserva(db: Session, *, cliente_id: int, lote_id: int, lotepreco_id: int, tipo_beneficio: str | None, quantidade: int) -> ReservaIngresso:
    lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).with_for_update().first()
    if not lote:
        raise HTTPException(404, "Lote não encontrado")
    preco = db.query(EventoLotePreco).filter(EventoLotePreco.lotepreco_id == lotepreco_id, EventoLotePreco.lote_id == lote_id, EventoLotePreco.situacao == "ATIVO").first()
    if not preco:
        raise HTTPException(404, "Modalidade de preço não encontrada")
    beneficio = (tipo_beneficio or "").strip().upper() or None
    if preco.tipopreco == "MEIA_LEGAL" and beneficio not in BENEFICIOS_COTA:
        raise HTTPException(422, "Informe um benefício válido para a meia-entrada legal")
    if preco.tipopreco == "MEIA_IDOSO" and beneficio != "IDOSO":
        raise HTTPException(422, "Selecione o benefício Pessoa idosa")
    agora = datetime.now()
    if lote.statuslote != "ATIVO" or (lote.dtiniciovenda and agora < lote.dtiniciovenda) or (lote.dtfimvenda and agora > lote.dtfimvenda):
        # O próximo lote pode abrir antes da data quando o anterior esgotar.
        if lote_atual_do_setor(db, lote, agora) is not lote:
            raise HTTPException(409, "Este lote não está disponível para venda")
    expirar_reservas(db)
    if lote_atual_do_setor(db, lote, agora) is not lote:
        raise HTTPException(409, "Outro lote está vigente para este setor")
    reservada_lote = quantidade_reservada(db, lote_id)
    if lote.qttotallote is not None and int(lote.qtvendidalote or 0) + reservada_lote + quantidade > int(lote.qttotallote):
        raise HTTPException(409, "O limite comercial deste lote foi atingido")
    reservada = int(db.query(func.coalesce(func.sum(ReservaIngresso.qtreservada), 0)).join(EventoLote, EventoLote.lote_id == ReservaIngresso.lote_id).filter(EventoLote.evento_id == lote.evento_id, ReservaIngresso.sitreserva.in_(STATUS_RESERVAM_ESTOQUE), ReservaIngresso.dtexpiracao > datetime.now()).scalar() or 0)
    vendida = int(db.query(func.coalesce(func.sum(EventoLote.qtvendidalote), 0)).filter(EventoLote.evento_id == lote.evento_id).scalar() or 0)
    capacidade_evento = int(db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0)).filter(EventoSetor.evento_id == lote.evento_id, EventoSetor.sitsetor == "ATIVO").scalar() or 0)
    if capacidade_evento <= 0 or vendida + reservada + quantidade > capacidade_evento:
        raise HTTPException(409, "A capacidade total do evento foi atingida")
    if preco.aplicacotalegal:
        usada = int(db.query(func.coalesce(func.sum(ReservaIngresso.qtreservada), 0)).join(EventoLotePreco, EventoLotePreco.lotepreco_id == ReservaIngresso.lotepreco_id).filter(ReservaIngresso.evento_id == lote.evento_id, EventoLotePreco.aplicacotalegal.is_(True), ReservaIngresso.sitreserva.in_(("PREENCHENDO", "AGUARDANDO_PAGAMENTO", "CONFIRMADA"))).scalar() or 0)
        if usada + quantidade > int(capacidade_evento * 0.40):
            raise HTTPException(409, "A cota de meia-entrada deste lote foi esgotada")
    loja = db.query(Loja).filter(Loja.loja_id == lote.loja_id).first()
    percentual = Decimal(str(loja.vrtaxaing or 0)) if loja else Decimal("0")
    minimo = Decimal(str(loja.vrtaxaminimaingresso or 0)) if loja else Decimal("0")
    unitario = Decimal(str(preco.vrpreco or 0)).quantize(Decimal("0.01"))
    taxa_unitaria = calcular_taxa_ingresso_unitaria(unitario, percentual, minimo)
    reserva = ReservaIngresso(
        organizacao_id=lote.organizacao_id, loja_id=lote.loja_id, cliente_id=cliente_id,
        evento_id=lote.evento_id, lote_id=lote.lote_id, lotepreco_id=preco.lotepreco_id, tipobeneficio=beneficio,
        qtreservada=quantidade, vrunitario=unitario, pctaxa=percentual,
        vrtaxa=taxa_unitaria,
        vrtotal=((unitario + taxa_unitaria) * quantidade).quantize(Decimal("0.01")),
        sitreserva="PREENCHENDO", dtexpiracao=agora + timedelta(minutes=5),
    )
    db.add(reserva)
    db.flush()
    return reserva
