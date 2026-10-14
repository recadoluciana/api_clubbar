from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventolotepreco import EventoLotePreco
from app.models.itvenda import ItVenda
from app.models.venda import Venda


def eh_modalidade_cortesia(preco: EventoLotePreco | None) -> bool:
    return bool(preco and (preco.tipopreco or "").strip().upper() == "CORTESIA")


def bloquear_evento_para_cortesia(db: Session, evento_id: int) -> None:
    """Serializa resgates e transferências de cortesias do mesmo evento."""
    db.query(Evento.evento_id).filter(
        Evento.evento_id == evento_id,
    ).with_for_update().first()


def validar_cortesia_unica_por_cpf(
    db: Session,
    *,
    evento_id: int,
    cpf: str,
    ignorar_itvenda_id: int | None = None,
) -> None:
    """Impede mais de uma cortesia ativa e resgatada por CPF no evento."""
    query = (
        db.query(ItVenda.itvenda_id)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .join(
            EventoLotePreco,
            EventoLotePreco.lotepreco_id == ItVenda.lotepreco_id,
        )
        .filter(
            EventoLote.evento_id == evento_id,
            ItVenda.cpfparticipante == cpf,
            ItVenda.sititvenda == "ATIVO",
            Venda.sitvenda == "PAGA",
            EventoLotePreco.tipopreco == "CORTESIA",
        )
    )
    if ignorar_itvenda_id is not None:
        query = query.filter(ItVenda.itvenda_id != ignorar_itvenda_id)
    if query.first():
        raise HTTPException(
            409,
            "Este CPF já possui uma cortesia resgatada para este evento.",
        )
