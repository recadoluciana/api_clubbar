from fastapi import HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho
from app.models.produto import Produto
from app.models.loja import Loja
from app.models.cardapio import Cardapio, CardapioItem, CardapioVersao
from app.services.taxa_service import calcular_taxa_ingresso_unitaria
from decimal import Decimal


def limpar_itens_indisponiveis(
    db: Session,
    carrinho_id: int,
    loja_id: int,
) -> int:
    """Remove do carrinho itens que não pertencem mais ao cardápio vigente."""
    itens = (
        db.query(ItCarrinho)
        .filter(ItCarrinho.carrinho_id == carrinho_id)
        .all()
    )
    if not itens:
        return 0

    ids_no_carrinho = {
        int(item.cardapioitem_id)
        for item in itens
        if item.cardapioitem_id is not None
    }
    agora = datetime.now()
    ids_disponiveis = {
        int(row[0])
        for row in (
            db.query(CardapioItem.cardapioitem_id)
            .join(
                CardapioVersao,
                CardapioVersao.cardapioversao_id
                == CardapioItem.cardapioversao_id,
            )
            .join(
                Cardapio,
                Cardapio.cardapio_id == CardapioVersao.cardapio_id,
            )
            .join(Produto, Produto.produto_id == CardapioItem.produto_id)
            .filter(
                CardapioItem.cardapioitem_id.in_(ids_no_carrinho),
                CardapioItem.sititem == "ATIVO",
                Produto.sitproduto == "ATIVO",
                Cardapio.loja_id == loja_id,
                Cardapio.sitcardapio == "ATIVO",
                CardapioVersao.statusversao.in_(["PUBLICADA", "PROGRAMADA"]),
                (CardapioVersao.dtiniciovigencia.is_(None))
                | (CardapioVersao.dtiniciovigencia <= agora),
                (CardapioVersao.dtfimvigencia.is_(None))
                | (CardapioVersao.dtfimvigencia >= agora),
            )
            .all()
        )
    }

    ids_remover = [
        item.itcarrinho_id
        for item in itens
        if item.cardapioitem_id is None
        or int(item.cardapioitem_id) not in ids_disponiveis
    ]
    if not ids_remover:
        return 0

    removidos = (
        db.query(ItCarrinho)
        .filter(ItCarrinho.itcarrinho_id.in_(ids_remover))
        .delete(synchronize_session=False)
    )
    db.flush()
    return int(removidos or 0)


def limpar_carrinhos_abertos_cliente(db: Session, cliente_id: int) -> int:
    carrinhos = (
        db.query(Carrinho)
        .filter(
            Carrinho.cliente_id == cliente_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .all()
    )
    total_removidos = sum(
        limpar_itens_indisponiveis(
            db,
            int(carrinho.carrinho_id),
            int(carrinho.loja_id),
        )
        for carrinho in carrinhos
    )
    if total_removidos:
        db.commit()
    return total_removidos

def get_carrinho(
    db: Session,
    cliente_id: int,
    loja_id: int,
    usuario_id: int | None = None,
) -> dict:
    # 1) acha carrinho ABERTO do cliente (trava o registro)
    carrinho_selec = (
        db.query(Carrinho)
        .filter(
            Carrinho.loja_id == loja_id,
            Carrinho.cliente_id == cliente_id,
            Carrinho.usuario_id == usuario_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .with_for_update()
        .first()
    )
    if not carrinho_selec:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado (ABERTO)")

    removidos = limpar_itens_indisponiveis(
        db,
        int(carrinho_selec.carrinho_id),
        int(carrinho_selec.loja_id),
    )
    if removidos:
        db.commit()

    # 2) busca itens do carrinho
    itens_car = (
        db.query(ItCarrinho)
        .filter(
            ItCarrinho.carrinho_id == carrinho_selec.carrinho_id,
            ItCarrinho.carrinho_id == Carrinho.carrinho_id
        )
        .all()
    )
    if not itens_car:
        raise HTTPException(status_code=400, detail="Carrinho sem itens")

    # 3) buscar na loja a taxa de ingresso e taxa de produto para armazenar como histórico
    loja_car = (
        db.query(Loja)
        .filter(
            Loja.loja_id == loja_id
        )
        .first()
    )
    if not loja_car:
        raise HTTPException(status_code=400, detail="Loja não encontrada")

    # 4) pega todos os produtos de uma vez (evita N+1 queries)
    produto_ids = list({it.produto_id for it in itens_car if it.produto_id is not None})
    produtos = (
        db.query(Produto)
        .filter(Produto.produto_id.in_(produto_ids))
        .all()
    )
    map_prod = {p.produto_id: p for p in produtos}
    cardapioitem_ids = list({
        it.cardapioitem_id for it in itens_car if it.cardapioitem_id is not None
    })
    itens_cardapio = (
        db.query(CardapioItem)
        .filter(CardapioItem.cardapioitem_id.in_(cardapioitem_ids))
        .all()
    ) if cardapioitem_ids else []
    map_item_cardapio = {
        item.cardapioitem_id: item for item in itens_cardapio
    }

    itens_agrupados = {}
    qt_total = 0
    total = 0.0
    percentual_taxa = 0.0
    valor_taxa = 0.0

    for it in itens_car:
        qt_aux = int(getattr(it, "qtitcarrinho", 1) or 1)

        prod = map_prod.get(it.produto_id)
        if not prod:
            raise HTTPException(
                status_code=400,
                detail=f"Produto {it.produto_id} não encontrado para item do carrinho",
            )

        nmproduto     = getattr(prod, "nmproduto", "Produto")
        item_cardapio = map_item_cardapio.get(it.cardapioitem_id)
        if not item_cardapio:
            raise HTTPException(
                status_code=409,
                detail=f"O produto '{nmproduto}' não está mais disponível no cardápio.",
            )
        vrprecoprod   = float(item_cardapio.vrpreco or 0)
        idtipoproduto = (getattr(prod, "idtipoproduto", "P") or "P").upper()

        subtotal = round(vrprecoprod * qt_aux, 2)
        qt_total += qt_aux
        total    += subtotal

        if idtipoproduto == "I":
            percentual_taxa = round(float(getattr(loja_car, "vrtaxaing", 0) or 0), 2)
            taxa_unitaria = calcular_taxa_ingresso_unitaria(
                Decimal(str(vrprecoprod)), Decimal(str(percentual_taxa)),
                Decimal(str(getattr(loja_car, "vrtaxaminimaingresso", 0) or 0)),
            )
            valor_taxa = float(taxa_unitaria * qt_aux)
        else:
            percentual_taxa = round(float(getattr(loja_car, "vrtaxaprod", 0) or 0), 2)
            valor_taxa = round(subtotal * (percentual_taxa / 100), 2)

        observacao = (getattr(it, "dsobsitcar", None) or "").strip()
        cardapioitem_id = getattr(it, "cardapioitem_id", None)
        chave = (int(it.produto_id), cardapioitem_id, observacao, vrprecoprod)
        if chave not in itens_agrupados:
            itens_agrupados[chave] = {
                "itcarrinho_id": it.itcarrinho_id,
                "produto_id": it.produto_id,
                "cardapioitem_id": cardapioitem_id,
                "nmproduto": nmproduto,
                "vrprecoprod": vrprecoprod,
                "qtitcarrinho": qt_aux,
                "dsobsitcar": observacao or None,
                "nmparticipante": it.nmparticipante,
                "cpfparticipante": it.cpfparticipante,
                "subtotal": subtotal,
                "idtipoproduto": idtipoproduto,
                "lote_id": getattr(it, "lote_id", None),
                "pctaxaitvenda": percentual_taxa,
                "vrtaxaitvenda": valor_taxa,
            }
        else:
            agrupado = itens_agrupados[chave]
            agrupado["qtitcarrinho"] += qt_aux
            agrupado["subtotal"] = round(agrupado["subtotal"] + subtotal, 2)
            agrupado["vrtaxaitvenda"] = round(
                agrupado["vrtaxaitvenda"] + valor_taxa, 2
            )

    itens_out = list(itens_agrupados.values())

    return {
        "carrinho_id": carrinho_selec.carrinho_id,
        "organizacao_id": carrinho_selec.organizacao_id,
        "usuario_id": carrinho_selec.usuario_id,
        "qt_total": qt_total,
        "total": total,
        "itens": itens_out,
    }
