from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.eventolote import EventoLote
from app.models.loja import Loja
from app.models.reserva_ingresso import ReservaIngresso


STATUS_RESERVAM_ESTOQUE = ("PREENCHENDO", "AGUARDANDO_PAGAMENTO")


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


def criar_reserva(db: Session, *, cliente_id: int, lote_id: int, quantidade: int) -> ReservaIngresso:
    lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).with_for_update().first()
    if not lote:
        raise HTTPException(404, "Lote não encontrado")
    agora = datetime.now()
    if lote.statuslote != "ATIVO" or (lote.dtiniciovenda and agora < lote.dtiniciovenda) or (lote.dtfimvenda and agora > lote.dtfimvenda):
        raise HTTPException(409, "Este lote não está disponível para venda")
    expirar_reservas(db, lote_id)
    reservada = quantidade_reservada(db, lote_id)
    vendida = int(lote.qtvendidalote or 0)
    if lote.qttotallote is not None and vendida + reservada + quantidade > int(lote.qttotallote):
        raise HTTPException(409, "Quantidade de ingressos indisponível neste lote")
    loja = db.query(Loja).filter(Loja.loja_id == lote.loja_id).first()
    percentual = Decimal(str(loja.vrtaxaing or 0)) if loja else Decimal("0")
    unitario = Decimal(str(lote.vrprecolote or 0)).quantize(Decimal("0.01"))
    reserva = ReservaIngresso(
        organizacao_id=lote.organizacao_id, loja_id=lote.loja_id, cliente_id=cliente_id,
        evento_id=lote.evento_id, lote_id=lote.lote_id,
        qtreservada=quantidade, vrunitario=unitario, pctaxa=percentual,
        vrtaxa=(unitario * percentual / Decimal("100")).quantize(Decimal("0.01")),
        vrtotal=(unitario * quantidade * (Decimal("1") + percentual / Decimal("100"))).quantize(Decimal("0.01")),
        sitreserva="PREENCHENDO", dtexpiracao=agora + timedelta(minutes=5),
    )
    db.add(reserva)
    db.flush()
    return reserva
