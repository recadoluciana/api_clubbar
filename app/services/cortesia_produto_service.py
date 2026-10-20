from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.cardapio import CardapioItem
from app.models.itvenda import ItVenda
from app.models.venda import Venda
from app.utils.datetime_utils import FUSO_BRASIL


def item_eh_cortesia(item: CardapioItem) -> bool:
    """Cortesias são emitidas exclusivamente pelas campanhas da loja."""
    return False


def _validar_periodo_e_limite(item: CardapioItem) -> None:
    agora = datetime.now(FUSO_BRASIL).replace(tzinfo=None)
    limite = int(item.qtcortesia or 0)

    if limite <= 0:
        raise HTTPException(409, "Cortesia esgotada.")
    if item.dtinicortesia is None or item.dtfimcortesia is None:
        raise HTTPException(409, "Cortesia indisponível no momento.")
    if agora < item.dtinicortesia or agora > item.dtfimcortesia:
        raise HTTPException(409, "Cortesia indisponível neste período.")


def _quantidade_resgatada(
    db: Session,
    *,
    cardapioitem_id: int,
    ignorar_venda_id: int | None = None,
) -> int:
    consulta = (
        db.query(func.coalesce(func.sum(ItVenda.qtitvenda), 0))
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(
            ItVenda.cardapioitem_id == cardapioitem_id,
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.sititvenda == "ATIVO",
            Venda.sitvenda == "PAGA",
        )
    )
    if ignorar_venda_id is not None:
        consulta = consulta.filter(ItVenda.venda_id != ignorar_venda_id)
    return int(consulta.scalar() or 0)


def validar_cliente_sem_cortesia_pendente(
    db: Session,
    *,
    cliente_id: int,
    produto_id: int,
    ignorar_venda_id: int | None = None,
) -> None:
    """Impede uma segunda cortesia válida e não retirada do mesmo produto."""
    hoje = datetime.now(FUSO_BRASIL).date()
    consulta = (
        db.query(ItVenda.itvenda_id)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.sitvenda == "PAGA",
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.produto_id == produto_id,
            ItVenda.sititvenda == "ATIVO",
            ItVenda.identregaitvenda == "NAO",
            ItVenda.vrunititvenda <= 0,
            or_(
                ItVenda.dtexpiraitvenda.is_(None),
                ItVenda.dtexpiraitvenda >= hoje,
            ),
        )
    )
    if ignorar_venda_id is not None:
        consulta = consulta.filter(ItVenda.venda_id != ignorar_venda_id)
    if consulta.first():
        raise HTTPException(
            409,
            "Você já possui uma cortesia deste produto válida e aguardando retirada.",
        )


def validar_cortesia_disponivel(
    db: Session,
    *,
    cardapioitem_id: int,
    quantidade: int,
    bloquear_item: bool = False,
    ignorar_venda_id: int | None = None,
) -> None:
    """Valida o saldo de uma cortesia e, quando necessário, o serializa.

    O bloqueio é utilizado na conclusão da venda para que resgates paralelos
    não consumam mais cortesias do que o limite configurado.
    """
    consulta = db.query(CardapioItem).filter(
        CardapioItem.cardapioitem_id == cardapioitem_id,
    )
    if bloquear_item:
        consulta = consulta.with_for_update()
    item = consulta.first()
    if not item or not item_eh_cortesia(item):
        return

    _validar_periodo_e_limite(item)
    quantidade_resgatada = _quantidade_resgatada(
        db,
        cardapioitem_id=cardapioitem_id,
        ignorar_venda_id=ignorar_venda_id,
    )
    if quantidade_resgatada + quantidade > int(item.qtcortesia):
        raise HTTPException(409, "Cortesia esgotada.")


def validar_cortesias_da_venda(db: Session, venda_id: int) -> None:
    """Confere o limite antes de transformar a venda em paga."""
    grupos = (
        db.query(
            ItVenda.cardapioitem_id,
            func.coalesce(func.sum(ItVenda.qtitvenda), 0).label("quantidade"),
        )
        .filter(
            ItVenda.venda_id == venda_id,
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.cardapioitem_id.is_not(None),
            ItVenda.vrunititvenda <= 0,
        )
        .group_by(ItVenda.cardapioitem_id)
        .order_by(ItVenda.cardapioitem_id)
        .all()
    )
    total_cortesias = sum(int(quantidade or 0) for _, quantidade in grupos)
    if total_cortesias > 1:
        raise HTTPException(
            422,
            "Cortesia limitada a 1 unidade por resgate.",
        )

    for cardapioitem_id, quantidade in grupos:
        if int(quantidade or 0) > 1:
            raise HTTPException(
                422,
                "Cortesia limitada a 1 unidade por transação.",
            )
        venda = db.query(Venda).filter(Venda.venda_id == venda_id).first()
        produto_id = (
            db.query(CardapioItem.produto_id)
            .filter(CardapioItem.cardapioitem_id == cardapioitem_id)
            .scalar()
        )
        if venda and venda.cliente_id and produto_id:
            validar_cliente_sem_cortesia_pendente(
                db,
                cliente_id=int(venda.cliente_id),
                produto_id=int(produto_id),
                ignorar_venda_id=venda_id,
            )
        validar_cortesia_disponivel(
            db,
            cardapioitem_id=int(cardapioitem_id),
            quantidade=int(quantidade or 0),
            bloquear_item=True,
            ignorar_venda_id=venda_id,
        )
