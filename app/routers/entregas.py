# app/routers/entregas.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.produto import Produto

router = APIRouter(prefix="/entregas", tags=["entregas"])


@router.get("/pendentes")
def listar_itens_nao_entregues(
    cliente_id      : int = Query(...),
    organizacao_id  : int = Query(...),
    loja_id         : int = Query(...),
    db              : Session = Depends(get_db),
):
    """
    Lista itens de vendas PAGAS que ainda NÃO foram entregues
    """

    itens = (
        db.query(
            ItVenda.itvenda_id,
            ItVenda.venda_id,
            Produto.produto_id,
            Produto.nmproduto,
            ItVenda.qtitvenda,
            ItVenda.vrunititvenda,
            ItVenda.dsobsitvenda,
            Venda.dtcriacao,
        )
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.organizacao_id == organizacao_id,
            Venda.loja_id == loja_id,
            Venda.sitvenda == "PAGA",
            ItVenda.identregaitvenda == "NAO",
        )
        .order_by(Venda.dtcriacao.desc())
        .all()
    )

    return [
        {
            "itvenda_id"    : itvenda.itvenda_id,
            "venda_id"      : itvenda.venda_id,
            "produto_id"    : itvenda.produto_id, 
            "nmproduto"     : itvenda.nmproduto,
            "qtitvenda"     : itvenda.qtitvenda,
            "vrunititvenda" : float(itvenda.vrunititvenda),
            "dsobsitvenda"  : itvenda.dsobsitvenda,
            "dtcriacao"     : itvenda.dtcriacao,
        }
        for itvenda in itens
    ]
