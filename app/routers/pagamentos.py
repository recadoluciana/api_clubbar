# app/routers/pagamentos.py
from __future__ import annotations

import os
from uuid import uuid4
from typing import Dict, List, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import delete

from app.database import get_db
from app.schemas.pagamentos import CheckoutCreateIn, CheckoutCreateOut, VendaStatusOut
from app.services.pagbank import criar_checkout_externo

from app.models.usuario import Usuario
from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho
from app.models.produto import Produto
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda


router = APIRouter(prefix="/pagamentos", tags=["pagamentos"])

PAGBANK_REDIRECT_URL = os.getenv("PAGBANK_REDIRECT_URL", "").strip()
PAGBANK_WEBHOOK_URL = os.getenv("PAGBANK_WEBHOOK_URL", "").strip()


def gerar_token_qr() -> str:
    return uuid4().hex


def _montar_items_pagbank(itens_car: List[ItCarrinho], produtos_map: Dict[int, Produto]) -> List[Dict[str, Any]]:
    items_pagbank: List[Dict[str, Any]] = []
    for it in itens_car:
        prod = produtos_map.get(int(it.produto_id))
        if not prod:
            raise HTTPException(400, f"Produto {it.produto_id} não encontrado")

        unit_amount_cents = int(round(float(prod.vrprecoprod) * 100))
        items_pagbank.append(
            {
                "reference_id": str(prod.produto_id),
                "name": (getattr(prod, "nmproduto", None) or f"Produto {prod.produto_id}"),
                "quantity": int(it.qtitcarrinho),
                "unit_amount": unit_amount_cents,
            }
        )
    return items_pagbank


def _calcular_total(itens_car: List[ItCarrinho], produtos_map: Dict[int, Produto]) -> float:
    total = 0.0
    for it in itens_car:
        prod = produtos_map.get(int(it.produto_id))
        if not prod:
            raise HTTPException(400, f"Produto {it.produto_id} não encontrado")
        total += float(prod.vrprecoprod) * int(it.qtitcarrinho)
    return total


@router.post("/checkout", response_model=CheckoutCreateOut)
async def criar_checkout(payload: CheckoutCreateIn, db: Session = Depends(get_db)):
    """
    Checkout idempotente (fluxo de bar):
    - acha carrinho ABERTO
    - se existe VENDA PENDENTE vinculada ao carrinho:
        - se pagvenda pendente tem pay_url -> devolve (reabre checkout)
        - se não tem pay_url -> cria checkout no PagBank e grava pay_url
    - se não existe venda pendente -> cria venda/itens/pagvenda e checkout e grava pay_url
    """

    print("CHECKOUT chamado:", payload.cliente_id, payload.organizacao_id, payload.loja_id)

    if not PAGBANK_WEBHOOK_URL:
        raise HTTPException(500, "PAGBANK_WEBHOOK_URL não configurada no .env")

    # 1) acha carrinho aberto do cliente
    carrinho = (
        db.query(Carrinho)
        .filter(
            Carrinho.organizacao_id == payload.organizacao_id,
            Carrinho.loja_id == payload.loja_id,
            Carrinho.cliente_id == payload.cliente_id,
            Carrinho.sitcarrinho == "ABERTO",
        )
        .with_for_update()
        .first()
    )
    if not carrinho:
        raise HTTPException(404, "Carrinho não encontrado (ABERTO)")

    itens_car = (
        db.query(ItCarrinho)
        .filter(ItCarrinho.carrinho_id == carrinho.carrinho_id)
        .all()
    )
    if not itens_car:
        raise HTTPException(400, "Carrinho sem itens")

    # 2) carrega produtos uma vez (serve pros dois fluxos)
    produto_ids = [int(it.produto_id) for it in itens_car]
    produtos = (
        db.query(Produto)
        .filter(Produto.produto_id.in_(produto_ids))
        .all()
    )
    produtos_map: Dict[int, Produto] = {int(p.produto_id): p for p in produtos}

    total = _calcular_total(itens_car, produtos_map)
    items_pagbank = _montar_items_pagbank(itens_car, produtos_map)

    try:
        # 3) procura venda pendente desse carrinho
        venda = (
            db.query(Venda)
            .filter(
                Venda.organizacao_id == payload.organizacao_id,
                Venda.loja_id == payload.loja_id,
                Venda.cliente_id == payload.cliente_id,
                Venda.carrinho_id == carrinho.carrinho_id,
                Venda.sitvenda == "PENDENTE",
            )
            .order_by(Venda.venda_id.desc())
            .first()
        )

        if venda:
            # pagamento pendente mais recente
            pag = (
                db.query(PagVenda)
                .filter(
                    PagVenda.venda_id == venda.venda_id,
                    PagVenda.sitpagvenda == "PENDENTE",
                )
                .order_by(PagVenda.pagvenda_id.desc())
                .first()
            )

            # ✅ se já tem pay_url, só devolve e o app reabre o mesmo checkout
            if pag and (pag.pay_url or "").strip():
                return CheckoutCreateOut(
                    venda_id=venda.venda_id,
                    pagvenda_id=pag.pagvenda_id,
                    pay_url=pag.pay_url,
                )

            # ✅ opcional: sincroniza itens da venda com o carrinho atual
            # (se você não quer mexer, pode remover esse bloco)
            db.execute(delete(ItVenda).where(ItVenda.venda_id == venda.venda_id))

            for it in itens_car:
                prod = produtos_map[int(it.produto_id)]
                qtd = int(it.qtitcarrinho)
                vr = float(prod.vrprecoprod)

                db.add(
                    ItVenda(
                        venda_id=venda.venda_id,
                        produto_id=int(it.produto_id),
                        qtitvenda=qtd,
                        vrunititvenda=vr,
                        dsobsitvenda=getattr(it, "dsobsitcar", None),
                        identregaitvenda="NAO",
                        qrtokenitvenda=gerar_token_qr(),
                    )
                )

            venda.totalvenda = float(total)

            # se não tinha pagvenda pendente, cria
            if not pag:
                pag = PagVenda(
                    venda_id=venda.venda_id,
                    dsmetodopag="OUTRO",
                    vrpagvenda=float(total),
                    sitpagvenda="PENDENTE",
                    reference_id=f"VENDA-{venda.venda_id}",
                    provedor="PAGBANK",
                )
                db.add(pag)
                db.flush()
            else:
                pag.vrpagvenda = float(total)
                if not getattr(pag, "reference_id", None):
                    pag.reference_id = f"VENDA-{venda.venda_id}"
                if not getattr(pag, "provedor", None):
                    pag.provedor = "PAGBANK"

            # cria checkout no PagBank e salva pay_url
            resp = await criar_checkout_externo(
                reference_id=f"VENDA-{venda.venda_id}",
                items=items_pagbank,
                redirect_url=PAGBANK_REDIRECT_URL or None,
                notification_urls=[PAGBANK_WEBHOOK_URL],
                payment_notification_urls=[PAGBANK_WEBHOOK_URL],
            )

            pag.checkout_id = resp.get("checkout_id")
            pag.pay_url = resp.get("pay_url")

            db.commit()
            return CheckoutCreateOut(
                venda_id=venda.venda_id,
                pagvenda_id=pag.pagvenda_id,
                pay_url=pag.pay_url,
            )

        # 4) se NÃO existe venda pendente, cria tudo do zero
        venda = Venda(
            organizacao_id=payload.organizacao_id,
            loja_id=payload.loja_id,
            cliente_id=payload.cliente_id,
            carrinho_id=carrinho.carrinho_id,
            dsplataforma=payload.plataforma,
            sitvenda="PENDENTE",
            totalvenda=float(total),
        )
        db.add(venda)
        db.flush()

        for it in itens_car:
            prod = produtos_map[int(it.produto_id)]
            db.add(
                ItVenda(
                    venda_id=venda.venda_id,
                    produto_id=int(it.produto_id),
                    qtitvenda=int(it.qtitcarrinho),
                    vrunititvenda=float(prod.vrprecoprod),
                    dsobsitvenda=getattr(it, "dsobsitcar", None),
                    identregaitvenda="NAO",
                    qrtokenitvenda=gerar_token_qr(),
                )
            )

        reference_id = f"VENDA-{venda.venda_id}"
        pag = PagVenda(
            venda_id=venda.venda_id,
            dsmetodopag="OUTRO",
            vrpagvenda=float(total),
            sitpagvenda="PENDENTE",
            reference_id=reference_id,
            provedor="PAGBANK",
        )
        db.add(pag)
        db.flush()

        resp = await criar_checkout_externo(
            reference_id=reference_id,
            items=items_pagbank,
            redirect_url=PAGBANK_REDIRECT_URL or None,
            notification_urls=[PAGBANK_WEBHOOK_URL],
            payment_notification_urls=[PAGBANK_WEBHOOK_URL],
        )

        pag.checkout_id = resp.get("checkout_id")
        pag.pay_url = resp.get("pay_url")

        db.commit()
        return CheckoutCreateOut(
            venda_id=venda.venda_id,
            pagvenda_id=pag.pagvenda_id,
            pay_url=pag.pay_url,
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Erro ao criar checkout: {e}")


@router.get("/vendas/{venda_id}/status", response_model=VendaStatusOut)
def status_venda(venda_id: int, db: Session = Depends(get_db)):
    venda = db.query(Venda).filter(Venda.venda_id == venda_id).first()
    if not venda:
        raise HTTPException(404, "Venda não encontrada")

    pag = (
        db.query(PagVenda)
        .filter(PagVenda.venda_id == venda_id)
        .order_by(PagVenda.pagvenda_id.desc())
        .first()
    )

    return VendaStatusOut(
        venda_id=venda.venda_id,
        sitvenda=venda.sitvenda,
        sitpagvenda=(pag.sitpagvenda if pag else None),
        totalvenda=float(venda.totalvenda or 0.0),
    )


@router.get("/vendas/{venda_id}/pay_url")
def get_pay_url(venda_id: int, db: Session = Depends(get_db)):
    pag = (
        db.query(PagVenda)
        .filter(PagVenda.venda_id == venda_id)
        .order_by(PagVenda.pagvenda_id.desc())
        .first()
    )
    if not pag or not (pag.pay_url or "").strip():
        raise HTTPException(404, "pay_url não encontrado para esta venda")
    return {"venda_id": venda_id, "pay_url": pag.pay_url}

@router.get("/pendente")
def venda_pendente(cliente_id: int, organizacao_id: int, loja_id: int, db: Session = Depends(get_db)):
    venda = (
        db.query(Venda)
        .filter(
            Venda.organizacao_id == organizacao_id,
            Venda.loja_id == loja_id,
            Venda.cliente_id == cliente_id,
            Venda.sitvenda == "PENDENTE",
        )
        .order_by(Venda.venda_id.desc())
        .first()
    )
    return {"venda_id": (venda.venda_id if venda else None)}

