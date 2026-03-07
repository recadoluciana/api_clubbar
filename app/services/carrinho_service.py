from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho
from app.models.produto import Produto

def get_carrinho(db: Session, cliente_id: int, organizacao_id: int, loja_id: int) -> dict:
    # 1) acha carrinho ABERTO do cliente (trava o registro)
    carrinho_selec = (
        db.query(Carrinho)
        .filter(
            Carrinho.organizacao_id == organizacao_id,
            Carrinho.loja_id == loja_id,
            Carrinho.cliente_id == cliente_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .with_for_update()
        .first()
    )
    if not carrinho:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado (ABERTO)")

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

    # 3) pega todos os produtos de uma vez (evita N+1 queries)
    produto_ids = list({it.produto_id for it in itens_car if it.produto_id is not None})
    produtos = (
        db.query(Produto)
        .filter(Produto.produto_id.in_(produto_ids))
        .all()
    )
    map_prod = {p.produto_id: p for p in produtos}

    itens_out = []
    qt_total = 0
    total = 0.0

    for it in itens_car:
        qt = int(getattr(it, "qt", 1) or 1)

        prod = map_prod.get(it.produto_id)
        if not prod:
            raise HTTPException(
                status_code=400,
                detail=f"Produto {it.produto_id} não encontrado para item do carrinho",
            )

        nmproduto = getattr(prod, "nmproduto", "Produto")
        vrprecoprod = float(getattr(prod, "vrprecoprod", 0) or 0)

        subtotal = vrprecoprod * qt
        qt_total += qt
        total += subtotal

        itens_out.append(
            {
                "itcarrinho_id": it.itcarrinho_id,
                "produto_id": it.produto_id,
                "nmproduto": nmproduto,
                "vrprecoprod": vrprecoprod,
                "qt": qt,
                "obs": getattr(it, "obs", None),
                "subtotal": subtotal,
            }
        )

    return {
        "carrinho_id": carrinho_selec.carrinho_id,
        "qt_total": qt_total,
        "total": total,
        "itens": itens_out,
    }