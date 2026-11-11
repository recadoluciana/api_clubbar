from fastapi import HTTPException
import re
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.itvenda import ItVenda
from app.models.venda import Venda
from app.models.cliente import Cliente


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
        db.query(ItVenda.itvenda_id, Cliente.nmcliente)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .outerjoin(Cliente, Cliente.cliente_id == Venda.cliente_id)
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .filter(
            EventoLote.evento_id == evento_id,
            func.replace(func.replace(func.replace(ItVenda.cpfparticipante, ".", ""), "-", ""), " ", "")
            == re.sub(r"\D", "", cpf),
            ItVenda.tipoitem == "INGRESSO",
            ItVenda.sititvenda.in_(["ATIVO", "CANCELAMENTO_SOLICITADO"]),
            Venda.sitvenda == "PAGA",
            ItVenda.vrunititvenda == 0,
        )
    )
    if ignorar_itvenda_id is not None:
        query = query.filter(ItVenda.itvenda_id != ignorar_itvenda_id)
    # Leitura atual sob o lock do evento, inclusive em REPEATABLE READ.
    ingresso = query.with_for_update().first()
    if ingresso:
        nome = (ingresso.nmcliente or '').strip().split()
        identificacao = nome[0] if nome else None
        mensagem = 'Este CPF já resgatou uma cortesia deste evento.'
        if identificacao:
            mensagem += f' O resgate foi feito pela conta {identificacao}.'
        raise HTTPException(
            409,
            mensagem,
        )
