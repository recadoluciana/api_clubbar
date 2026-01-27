from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.venda import Venda
from app.models.itvenda import ItVenda  # ajuste o nome do model/arquivo
from app.models.produto import Produto  # 👈 novo

router = APIRouter(prefix="/compras", tags=["compras"])

@router.get("")
def listar_compras(
    cliente_id: int,
    incluir_itens: bool = True,
    db: Session = Depends(get_db),
):
    # 1) Vendas do cliente
    vendas = (
        db.query(Venda)
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.sitvenda   == "PAGA"
        )
        .order_by(Venda.dtcriacao.desc())
        .all()
    )

    if not vendas:
        return []

    if not incluir_itens:
        return [
            {
                "venda_id": v.venda_id,
                "sitvenda": v.sitvenda,
                "totalvenda": float(v.totalvenda),
                "dtcriacao": v.dtcriacao,
                "carrinho_id": v.carrinho_id,
                "dsplataforma": v.dsplataforma,
            }
            for v in vendas
        ]

    venda_ids = [v.venda_id for v in vendas]

    # 2) Itens + nome do produto (JOIN)
    itens_rows = (
        db.query(ItVenda, Produto.nmproduto)
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .filter(ItVenda.venda_id.in_(venda_ids))
        .all()
    )

    itens_por_venda = {}
    for it, nmproduto in itens_rows:
        itens_por_venda.setdefault(it.venda_id, []).append({
            "itvenda_id": getattr(it, "itvenda_id", None),
            "produto_id": getattr(it, "produto_id", None),
            "nmproduto" : nmproduto,  # ✅ aqui
            "qtitvenda" : it.qtitvenda,
            "vrunititvenda": float(it.vrunititvenda),
            "identregaitvenda": it.identregaitvenda,
            "dtentregaitvenda": it.dtentregaitvenda,
            "userentregaitvenda": it.userentregaitvenda,
            "nmuserentregaitvenda": it.nmuserentregaitvenda,
            "dsobsitvenda": it.dsobsitvenda,
        })

    # 3) Resposta final
    resp = []
    for v in vendas:
        resp.append({
            "venda_id": v.venda_id,
            "organizacao_id": v.organizacao_id,
            "loja_id": v.loja_id,
            "cliente_id": v.cliente_id,
            "dsplataforma": v.dsplataforma,
            "sitvenda": v.sitvenda,
            "totalvenda": float(v.totalvenda),
            "dtcriacao": v.dtcriacao,
            "dtultatu": v.dtultatu,
            "carrinho_id": v.carrinho_id,
            "itens": itens_por_venda.get(v.venda_id, []),
        })

    return resp