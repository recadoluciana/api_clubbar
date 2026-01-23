# app/routers/pagamentos.py
from __future__ import annotations

import os
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pagamentos import CheckoutCreateIn, CheckoutCreateOut, VendaStatusOut
from app.services.pagbank import criar_checkout_externo

# Ajuste estes imports para os seus models reais:
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
    return uuid4().hex  # simples e bem único


@router.post("/checkout", response_model=CheckoutCreateOut)
async def criar_checkout(payload: CheckoutCreateIn, db: Session = Depends(get_db)):
    """
    Fluxo:
    - cria VENDA (ABERTA)
    - cria ITVENDAS copiando ITCARRINHO
    - cria PAGVENDA (PENDENTE) com reference_id
    - cria Checkout PagBank e grava checkout_id + pay_url
    - retorna pay_url pro app abrir
    """
    if not PAGBANK_WEBHOOK_URL:
        raise HTTPException(500, "PAGBANK_WEBHOOK_URL não configurada no .env")

    # 1) carrinho do cliente
    carrinho = (
        db.query(Carrinho)
        .filter(
            Carrinho.organizacao_id == payload.organizacao_id,
            Carrinho.loja_id == payload.loja_id,
            Carrinho.cliente_id == payload.cliente_id,
            Carrinho.sitcarrinho == "ABERTO"
        )
        .first()
    )
    if not carrinho:
        raise HTTPException(404, "Carrinho não encontrado")

    itens_car = db.query(ItCarrinho).filter(ItCarrinho.carrinho_id == carrinho.carrinho_id).all()
    if not itens_car:
        raise HTTPException(400, "Carrinho sem itens")

    # 2) monta itens + total usando Produto
    produtos_map = {}
    produto_ids = [it.produto_id for it in itens_car]
    for p in db.query(Produto).filter(Produto.produto_id.in_(produto_ids)).all():
        produtos_map[p.produto_id] = p

    total = 0.0
    for it in itens_car:
        prod = produtos_map.get(it.produto_id)
        if not prod:
            raise HTTPException(400, f"Produto {it.produto_id} não encontrado")
        total += float(prod.vrprecoprod) * int(it.qtitcarrinho)

    # 3) transação no banco
    try:
        venda = Venda(
            organizacao_id=payload.organizacao_id,
            loja_id=payload.loja_id,
            cliente_id=payload.cliente_id,
            carrinho_id=carrinho.carrinho_id,
            dsplataforma=payload.plataforma,
            sitvenda="PENDENTE",
            totalvenda=total,
        )
        db.add(venda)
        db.flush()  # pega venda_id

        # itens da venda
        for it in itens_car:
            prod = produtos_map[it.produto_id]
            item_venda = ItVenda(
                venda_id=venda.venda_id,
                produto_id=it.produto_id,
                qtitvenda=int(it.qtitcarrinho),
                vrunititvenda=float(prod.vrprecoprod),
                dsobsitvenda=getattr(it, "dsobsitcar", None),
                identregaitvenda="NAO",
                qrtokenitvenda=gerar_token_qr(),
            )
            db.add(item_venda)

        # pagamento pendente (você escolhe OUTRO aqui porque o PagBank checkout pode aceitar meios diferentes)
        reference_id = f"VENDA-{venda.venda_id}"
        pag = PagVenda(
            venda_id=venda.venda_id,
            dsmetodopag="OUTRO",
            vrpagvenda=total,
            sitpagvenda="PENDENTE",
            # se você adicionar as colunas sugeridas:
            reference_id=reference_id,
            provedor="PAGBANK",
        )
        db.add(pag)
        db.flush()  # pega pagvenda_id

        # 4) itens pro PagBank (formato típico: reference_id, name, quantity, unit_amount em centavos)
        items_pagbank = []
        for it in itens_car:
            prod = produtos_map[it.produto_id]
            unit_amount_cents = int(round(float(prod.vrprecoprod) * 100))
            items_pagbank.append(
                {
                    "reference_id": str(prod.produto_id),
                    "name": getattr(prod, "nmproduto", f"Produto {prod.produto_id}"),
                    "quantity": int(it.qtitcarrinho),
                    "unit_amount": unit_amount_cents,
                }
            )

        # 5) cria checkout no PagBank e salva url
        resp = await criar_checkout_externo(
            reference_id=reference_id,
            items=items_pagbank,
            redirect_url=PAGBANK_REDIRECT_URL or None,
            notification_urls=[PAGBANK_WEBHOOK_URL],  # webhook do checkout :contentReference[oaicite:10]{index=10}
        )

        # grava ids/links (precisa das colunas no pagvenda)
        pag.checkout_id = resp["checkout_id"]
        pag.pay_url = resp["pay_url"]

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
        totalvenda=float(venda.totalvenda),
    )
