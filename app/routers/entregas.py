# app/routers/entregas.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, date
from sqlalchemy import or_

from app.database import get_db
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.produto import Produto

router = APIRouter(prefix="/entregas", tags=["entregas"])


@router.get("/pendentes")
def listar_itens_nao_entregues(
    cliente_id: int = Query(...),
    organizacao_id: int = Query(...),
    loja_id: int = Query(...),
    db: Session = Depends(get_db),
):
    """
    Lista itens de vendas PAGAS que ainda NÃO foram entregues
    """

    hoje = date.today()

    itens = (
        db.query(
            ItVenda.itvenda_id.label("itvenda_id"),
            ItVenda.venda_id.label("venda_id"),
            Produto.produto_id.label("produto_id"),
            Produto.nmproduto.label("nmproduto"),
            ItVenda.qtitvenda.label("qtitvenda"),
            ItVenda.vrunititvenda.label("vrunititvenda"),
            ItVenda.dsobsitvenda.label("dsobsitvenda"),
            ItVenda.dtexpiraitvenda.label("dtexpiraitvenda"),
            Venda.dtcriacao.label("dtcriacao"),
            Venda.loja_id.label("loja_id"),
        )
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.sitvenda == "PAGA",
            ItVenda.identregaitvenda == "NAO",
            or_(
                ItVenda.dtexpiraitvenda == None,          # sem validade => deixa passar
                ItVenda.dtexpiraitvenda >= hoje,          # ainda válido
            )
        )
        .order_by(Venda.loja_id.asc(),Venda.dtcriacao.desc())
        .all()
    )

    return [
        {
            "itvenda_id": row.itvenda_id,
            "venda_id": row.venda_id,
            "produto_id": row.produto_id,
            "nmproduto": row.nmproduto,
            "qtitvenda": row.qtitvenda,
            "vrunititvenda": float(row.vrunititvenda or 0.0),
            "dsobsitvenda": row.dsobsitvenda,
            "dtexpiraitvenda": row.dtexpiraitvenda,  # ISO padrão (ex: 2026-05-03)
            "dtexpiraitvenda_fmt": row.dtexpiraitvenda.strftime("%d/%m/%Y") if row.dtexpiraitvenda else None,
            "dtcriacao": row.dtcriacao,
            "dtcriacao_fmt": row.dtcriacao.strftime("%d/%m/%Y") if row.dtcriacao else None,
            "loja_id": row.loja_id,
        }
        for row in itens
    ]


@router.post("/{itvenda_id}/entregarproduto")
def entregar_produto(itvenda_id: int, usuario_id: int, db: Session = Depends(get_db)):
    item = db.query(ItVenda).filter(ItVenda.itvenda_id == itvenda_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")

    # evita entregar 2x
    if getattr(item, "identregaitvenda", None) == "SIM":
        return {
            "ok": True,
            "already": True,
            "msg": "Este produto já foi entregue.",
            "itvenda_id": itvenda_id,
            "dtentregaitvenda": item.dtentregaitvenda.isoformat() if item.dtentregaitvenda else None,
            "userentregaitvenda": getattr(item, "userentregaitvenda", None),
            "nmuserentregaitvenda": getattr(item, "nmuserentregaitvenda", None),
        }

    item.identregaitvenda     = "SIM"
    item.dtentregaitvenda     = datetime.now()
    item.userentregaitvenda   = usuario_id  # ou item.usuario_id_entregou (ajuste conforme sua coluna)
    item.nmuserentregaitvenda = str(usuario_id)

    db.commit()
    db.refresh(item)

    return {
        "ok": True,
        "itvenda_id"           : itvenda_id,
        "identregaitvenda"     : item.identregaitvenda,
        "dtentregaitvenda"     : item.dtentregaitvenda.isoformat(),
        "userentregaitvenda"   : usuario_id,
        "nmuserentregaitvenda" : item.nmuserentregaitvenda,
    }

@router.get("/{itvenda_id}/status")
def status_entrega(itvenda_id: int, db: Session = Depends(get_db)):
    
    item = db.query(ItVenda).filter(ItVenda.itvenda_id == itvenda_id).first()
    
    if not item:
        print("deu status_code 404, nao achou o item", itvenda_id)
        raise HTTPException(status_code=404, detail="Item não encontrado")

    entregue = (item.identregaitvenda == "SIM")

    return {
        "ok": True,
        "itvenda_id": itvenda_id,
        "entregue": entregue,
        "identregaitvenda": item.identregaitvenda,
        "dtentregaitvenda": item.dtentregaitvenda.isoformat() if item.dtentregaitvenda else None,
        "userentregaitvenda": item.userentregaitvenda,
        "nmuserentregaitvenda": item.nmuserentregaitvenda,
    }

@router.get("/entregues")
def listar_entregues_por_usuario(
    usuario_id: int = Query(...),
    organizacao_id: int = Query(...),
    loja_id: int = Query(...),
    horas: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """
    Lista itens entregues pelo usuário logado nas últimas X horas (padrão 24h),
    mais recentes primeiro.
    """

    desde = datetime.now() - timedelta(hours=horas)

    itens = (
        db.query(
            ItVenda.itvenda_id.label("itvenda_id"),
            ItVenda.venda_id.label("venda_id"),
            ItVenda.qtitvenda.label("qtitvenda"),
            ItVenda.vrunititvenda.label("vrunititvenda"),
            ItVenda.dsobsitvenda.label("dsobsitvenda"),
            ItVenda.dtentregaitvenda.label("dtentregaitvenda"),
            ItVenda.userentregaitvenda.label("userentregaitvenda"),
            ItVenda.nmuserentregaitvenda.label("nmuserentregaitvenda"),
            Produto.produto_id.label("produto_id"),
            Produto.nmproduto.label("nmproduto"),
        )
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .filter(
            Venda.organizacao_id == organizacao_id,
            Venda.loja_id == loja_id,

            # entregue (você usa SIM / ENTREGUE em lugares diferentes — aceito ambos)
            or_(
                ItVenda.identregaitvenda == "SIM",
                ItVenda.identregaitvenda == "ENTREGUE",
            ),

            ItVenda.userentregaitvenda == usuario_id,
            ItVenda.dtentregaitvenda != None,
            ItVenda.dtentregaitvenda >= desde,
        )
        .order_by(ItVenda.dtentregaitvenda.desc())
        .all()
    )

    return [
        {
            "itvenda_id": r.itvenda_id,
            "venda_id": r.venda_id,
            "qtitvenda": int(r.qtitvenda or 0),
            "vrunititvenda": float(r.vrunititvenda or 0.0),
            "dsobsitvenda": r.dsobsitvenda,
            "dtentregaitvenda": r.dtentregaitvenda.isoformat() if r.dtentregaitvenda else None,
            "dtentregaitvenda_fmt": r.dtentregaitvenda.strftime("%d/%m/%Y %H:%M") if r.dtentregaitvenda else None,
            "userentregaitvenda": r.userentregaitvenda,
            "nmuserentregaitvenda": r.nmuserentregaitvenda,
            "produto_id": r.produto_id,
            "nmproduto": r.nmproduto,
        }
        for r in itens
    ]
