from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.produto import Produto
from app.models.loja import Loja


def formatar_data_br(dt):
    if not dt:
        return ""

    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", ""))
        except:
            return dt

    return dt.strftime("%d/%m/%Y %H:%M")

router = APIRouter(prefix="/compras", tags=["compras"])

@router.get("")
def listar_compras(
    cliente_id: int,
    incluir_itens: bool = True,
    db: Session = Depends(get_db),
):
    # 1) Vendas do cliente + nome da loja
    vendas = (
        db.query(Venda, Loja.nmloja)
        .join(Loja, (Loja.organizacao_id == Venda.organizacao_id) & (Loja.loja_id == Venda.loja_id))
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.sitvenda == "PAGA"
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
                "organizacao_id": v.organizacao_id,
                "loja_id": v.loja_id,
                "nmloja": nmloja,              # ✅ aqui
                "cliente_id": v.cliente_id,
                "sitvenda": v.sitvenda,
                "totalvenda": float(v.totalvenda),
                "dtcriacao": formatar_data_br(v.dtcriacao),
                "carrinho_id": v.carrinho_id,
                "dsplataforma": v.dsplataforma,
            }
            for v, nmloja in vendas
        ]

    venda_ids = [v.venda_id for v, _ in vendas]   # ✅ aqui

    # 2) Itens + nome do produto
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
            "nmproduto": nmproduto,
            "qtitvenda": it.qtitvenda,
            "vrunititvenda": float(it.vrunititvenda),
            "identregaitvenda": it.identregaitvenda,
            "dtentregaitvenda": formatar_data_br(it.dtentregaitvenda),
            "userentregaitvenda": it.userentregaitvenda,
            "nmuserentregaitvenda": it.nmuserentregaitvenda,
            "dsobsitvenda": it.dsobsitvenda,
        })

    # 3) Resposta final
    resp = []
    for v, nmloja in vendas:                      # ✅ aqui
        resp.append({
            "venda_id": v.venda_id,
            "organizacao_id": v.organizacao_id,
            "loja_id": v.loja_id,
            "nmloja": nmloja,                     # ✅ aqui
            "cliente_id": v.cliente_id,
            "dsplataforma": v.dsplataforma,
            "sitvenda": v.sitvenda,
            "totalvenda": float(v.totalvenda),
            "dtcriacao": formatar_data_br(v.dtcriacao),   # ✅ agora BR
            "dtultatu": formatar_data_br(v.dtultatu),     # ✅ agora correto
            "carrinho_id": v.carrinho_id,
            "itens": itens_por_venda.get(v.venda_id, []),
        })

    return resp
