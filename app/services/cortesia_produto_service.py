from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.cardapio import CardapioItem
from app.models.itvenda import ItVenda
from app.models.venda import Venda
from app.utils.datetime_utils import FUSO_BRASIL


def item_eh_cortesia(item: CardapioItem) -> bool:
    """Indica se a regra comercial do item reduz seu preço a zero."""
    preco = Decimal(str(item.vrpreco or 0))
    if preco <= 0:
        return True

    tipo = (item.tipodesconto or "NENHUM").upper()
    desconto = Decimal(str(item.vrdesconto or 0))
    return (tipo == "PERCENTUAL" and desconto >= Decimal("100")) or (
        tipo == "VALOR" and desconto >= preco
    )


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
    for cardapioitem_id, quantidade in grupos:
        if int(quantidade or 0) > 1:
            raise HTTPException(
                422,
                "Cortesia limitada a 1 unidade por transação.",
            )
        validar_cortesia_disponivel(
            db,
            cardapioitem_id=int(cardapioitem_id),
            quantidade=int(quantidade or 0),
            bloquear_item=True,
            ignorar_venda_id=venda_id,
        )
