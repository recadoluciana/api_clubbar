from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import get_db
from app.schemas.carrinho import AddItemIn, AddItemOut, CarrinhoItemAgrupadoOut
from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho
from app.models.produto import Produto
from app.models.eventolote import EventoLote

router = APIRouter(prefix="/carrinho", tags=["Carrinho"])


@router.post("/itens", response_model=AddItemOut)
def adicionar_item(payload: AddItemIn, db: Session = Depends(get_db)):


    def get_or_create_produto_por_lote(organizacao_id: int, loja_id: int, lote_id: int) -> Produto:


        # valida lote
        lote = (
            db.query(EventoLote)
            .filter(
                EventoLote.lote_id == lote_id,
                EventoLote.organizacao_id == organizacao_id,
                EventoLote.loja_id == loja_id,
                EventoLote.statuslote == "ATIVO",
            )
            .first()
        )
        if not lote:
            raise HTTPException(status_code=404, detail="Lote não encontrado ou inativo")

        # procura produto “espelho” pelo lote_id
        produto = (
            db.query(Produto)
            .filter(
                Produto.organizacao_id == organizacao_id,
                Produto.loja_id == loja_id,
                Produto.lote_id == lote_id,
                Produto.sitproduto == "ATIVO",
            )
            .first()
        )
        if produto:
            print("entrei na funcao produto por loja", produto)
            return produto


        # cria produto “espelho”
        produto = Produto(
            organizacao_id=organizacao_id,
            loja_id=loja_id,
            lote_id=lote_id,
            idtipoproduto="I",
            nmproduto=lote.nmlote,
            vrprecoprod=lote.vrprecolote,
            sitproduto="ATIVO",
        )
        db.add(produto)

        try:
            db.flush()  # garante produto_id aqui
        except IntegrityError:
            db.rollback()
            produto = (
                db.query(Produto)
                .filter(
                    Produto.organizacao_id == organizacao_id,
                    Produto.loja_id == loja_id,
                    Produto.lote_id == lote_id,
                )
                .first()
            )
            if not produto:
                raise
        return produto

    # 1) define produto_id_final dependendo do tipo
    if payload.idtipoproduto == "P":
        produto = (
            db.query(Produto)
            .filter(
                Produto.produto_id == payload.produto_id,
                Produto.organizacao_id == payload.organizacao_id,
                Produto.loja_id == payload.loja_id,
                Produto.sitproduto == "ATIVO",
                Produto.idtipoproduto == "P",
            )
            .first()
        )
        if not produto:
            raise HTTPException(status_code=404, detail="Produto não encontrado ou inativo")
        produto_id_final = int(produto.produto_id)
        lote_id_final = None

    else:  # "I"
        produto_ingresso = get_or_create_produto_por_lote(
            organizacao_id=payload.organizacao_id,
            loja_id=payload.loja_id,
            lote_id=payload.lote_id,
        )
        produto_id_final = int(produto_ingresso.produto_id)
        lote_id_final = int(payload.lote_id)

    # 2) carrinho aberto do cliente
    carr = (
        db.query(Carrinho)
        .filter(
            Carrinho.cliente_id == payload.cliente_id,
            Carrinho.organizacao_id == payload.organizacao_id,
            Carrinho.loja_id == payload.loja_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .first()
    )
    if not carr:
        carr = Carrinho(
            organizacao_id=payload.organizacao_id,
            loja_id=payload.loja_id,
            cliente_id=payload.cliente_id,
        )
        db.add(carr)
        db.flush()

    # 3) cria item (produto_id NOT NULL garantido)
    item = ItCarrinho(
        carrinho_id=int(carr.carrinho_id),
        produto_id=produto_id_final,
        qtitcarrinho=int(payload.qt),
        dsobsitcar=(payload.obs or None),
        lote_id=lote_id_final,  # ✅ NUNCA "" (string)
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    return AddItemOut(
        carrinho_id=int(carr.carrinho_id),
        itcarrinho_id=int(item.itcarrinho_id),
        produto_id=int(item.produto_id),
        qt=int(item.qtitcarrinho),
        obs=item.dsobsitcar,
    )

@router.get("/qt")
def get_qt_carrinho(cliente_id: int, organizacao_id: int, loja_id: int, db: Session = Depends(get_db)):
    # 1) encontra carrinho único
    carr = (
        db.query(Carrinho)
        .filter(
            Carrinho.cliente_id == cliente_id,
            Carrinho.organizacao_id == organizacao_id,
            Carrinho.loja_id == loja_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .first()
    )

    if not carr:
        return {"carrinho_id": None, "qt": 0}

    row = (
        db.query(
            func.coalesce(func.sum(ItCarrinho.qtitcarrinho), 0).label("qt"),
            func.coalesce(func.sum(ItCarrinho.qtitcarrinho * Produto.vrprecoprod), 0).label("total"),
        )
        .join(Produto, Produto.produto_id == ItCarrinho.produto_id)
        .filter(ItCarrinho.carrinho_id    == carr.carrinho_id)
        .first()
    )

    qt = int(row.qt or 0)
    total = float(row.total or 0.0)

    return {"carrinho_id": int(carr.carrinho_id), "qt": qt, "total": total}

@router.get("/itens")
def listar_itens(
    cliente_id: int,
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
):
    carr = (
        db.query(Carrinho)
        .filter(
            Carrinho.cliente_id == int(cliente_id),
            Carrinho.organizacao_id == int(organizacao_id),
            Carrinho.loja_id == int(loja_id),
            Carrinho.sitcarrinho == "ABERTO",
        )
        .first()
    )

    if not carr:
        return {
            "carrinho_id": None,
            "qt_total": 0,
            "total": 0.0,
            "itens": [],
        }

    rows = (
        db.query(
            ItCarrinho.itcarrinho_id,
            ItCarrinho.carrinho_id,
            ItCarrinho.produto_id,
            ItCarrinho.qtitcarrinho,
            ItCarrinho.dsobsitcar,
            Produto.nmproduto,
            Produto.vrprecoprod,
        )
        .join(Produto, Produto.produto_id == ItCarrinho.produto_id)
        .filter(ItCarrinho.carrinho_id == carr.carrinho_id)
        .order_by(ItCarrinho.itcarrinho_id.desc())
        .all()
    )

    itens = []
    total = 0.0
    qt_total = 0

    for r in rows:
        qtd = int(r.qtitcarrinho or 0)
        preco = float(r.vrprecoprod or 0.0)
        subtotal = preco * qtd

        qt_total += qtd
        total += subtotal

        itens.append(
            {
                "itcarrinho_id": int(r.itcarrinho_id),
                "produto_id": int(r.produto_id),
                "nmproduto": r.nmproduto,
                "vrprecoprod": preco,
                "qt": qtd,
                "obs": r.dsobsitcar,
                "subtotal": float(subtotal),
            }
        )

    return {
        "carrinho_id": int(carr.carrinho_id),
        "qt_total": int(qt_total),
        "total": float(total),
        "itens": itens,
    }

@router.delete("/{carrinho_id}/produto/{produto_id}/um")
def remover_uma_unidade(carrinho_id: int, produto_id: int, db: Session = Depends(get_db)):
    res = db.execute(
        text("""
            DELETE FROM itcarrinho
            WHERE carrinho_id = :cid AND produto_id = :pid
            ORDER BY dtcriacao DESC, itcarrinho_id DESC
            LIMIT 1
        """),
        {"cid": carrinho_id, "pid": produto_id},
    )
    db.commit()

    if res.rowcount == 0:
        raise HTTPException(status_code=404, detail="Produto não encontrado no carrinho")

    return {"ok": True, "msg": "Removida 1 unidade do produto do carrinho"}


@router.get("/itens/agrupados", response_model=list[CarrinhoItemAgrupadoOut])
def get_itens_carrinho(
    cliente_id: int,
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
):
    # (opcional) normaliza observação: NULL e "" viram ""
    # obs_norm = func.coalesce(func.nullif(ItCarrinho.dsobsitcar, ""), "")
    obs_norm = ItCarrinho.dsobsitcar

    q = (
        db.query(
            Carrinho.organizacao_id.label("organizacao_id"),
            Carrinho.loja_id.label("loja_id"),
            Carrinho.cliente_id.label("cliente_id"),
            Carrinho.carrinho_id.label("carrinho_id"),

            ItCarrinho.produto_id.label("produto_id"),
            obs_norm.label("dsobsitcar"),
            func.sum(ItCarrinho.qtitcarrinho).label("qtitcarrinho"),

            Produto.nmproduto.label("nmproduto"),
            Produto.vrprecoprod.label("vrprecoprod"),
            Produto.img.label("img"),
        )
        .join(ItCarrinho, ItCarrinho.carrinho_id == Carrinho.carrinho_id)
        .join(
            Produto,
            (Produto.produto_id == ItCarrinho.produto_id)
            & (Produto.organizacao_id == Carrinho.organizacao_id)
            & (Produto.loja_id == Carrinho.loja_id),
        )
        .filter(Carrinho.cliente_id == int(cliente_id))
        .filter(Carrinho.organizacao_id == int(organizacao_id))
        .filter(Carrinho.loja_id == int(loja_id))
        .filter(Carrinho.sitcarrinho == 'ABERTO')
        .group_by(
            Carrinho.organizacao_id,
            Carrinho.loja_id,
            Carrinho.cliente_id,
            Carrinho.carrinho_id,

            ItCarrinho.produto_id,
            obs_norm,

            Produto.nmproduto,
            Produto.vrprecoprod,
            Produto.img,
        )
        .order_by(Produto.nmproduto.asc(), obs_norm.asc())
    )

    rows = q.all()

    return [
        {
            "organizacao_id": r.organizacao_id,
            "loja_id": r.loja_id,
            "cliente_id": r.cliente_id,
            "carrinho_id": r.carrinho_id,
            "produto_id": r.produto_id,
            "dsobsitcar": r.dsobsitcar,
            "qtitcarrinho": int(r.qtitcarrinho or 0),
            "nmproduto": r.nmproduto,
            "vrprecoprod": float(r.vrprecoprod) if r.vrprecoprod is not None else None,
            "img": r.img,
        }
        for r in rows
    ]