from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import HTTPException
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda

import uuid


def gerar_token_qr() -> str:
    return uuid.uuid4().hex


async def criar_ou_obter_venda_idempotente(
    db: Session,
    *,
    cliente_id: int,
    loja_id: int,
    organizacao_id: int,
    carrinho: Dict[str, Any],
    chave: Optional[str] = None,
    plataforma: str = "ANDROID",
    metodo_pagamento: str = "CREDITO",  # PIX, CREDITO, DEBITO
) -> Dict[str, Any]:

    carrinho_id = int(carrinho.get("carrinho_id") or 0)
    itens = carrinho.get("itens", [])
    total = float(carrinho.get("total") or 0)

    if not carrinho_id:
        raise HTTPException(status_code=400, detail="carrinho_id inválido")

    if not itens:
        raise HTTPException(status_code=400, detail="Carrinho sem itens")

    metodo_pagamento = (metodo_pagamento or "CREDITO").strip().upper()

    if metodo_pagamento == "CREDIT_CARD":
        metodo_pagamento = "CREDITO"
    elif metodo_pagamento == "DEBIT_CARD":
        metodo_pagamento = "DEBITO"
    elif metodo_pagamento not in ["PIX", "CREDITO", "DEBITO", "OUTRO"]:
        metodo_pagamento = "OUTRO"

    ## testa venda PAGA PARA EVITAR duplicidade de criação da venda
    venda_paga = (
        db.query(Venda)
        .filter(
            Venda.loja_id == loja_id,
            Venda.cliente_id == cliente_id,
            Venda.carrinho_id == carrinho_id,
            Venda.sitvenda == "PAGO",
        )
        .order_by(Venda.venda_id.desc())
        .first()
    )

    if venda_paga:
        pag = (
            db.query(PagVenda)
            .filter(PagVenda.venda_id == venda_paga.venda_id)
            .order_by(PagVenda.pagvenda_id.desc())
            .first()
        )

        return {
            "venda_id": int(venda_paga.venda_id),
            "pagvenda_id": int(pag.pagvenda_id) if pag else 0,
            "reference_id": pag.reference_id if pag else f"VENDA-{venda_paga.venda_id}",
            "already_paid": True,
        }    
    ## >>>>>>>>>>>>>>>>>>>>>>>>>>>>>> fim >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

    venda = (
        db.query(Venda)
        .filter(
            Venda.loja_id == loja_id,
            Venda.cliente_id == cliente_id,
            Venda.carrinho_id == carrinho_id,
            Venda.sitvenda == "PENDENTE",
        )
        .order_by(Venda.venda_id.desc())
        .first()
    )

    def _sync_itens_venda(venda_id: int) -> None:
        db.execute(delete(ItVenda).where(ItVenda.venda_id == venda_id))

        agora = datetime.now()
        fim = agora + timedelta(days=30)


        for it in itens:
            produto_id = int(it["produto_id"])
            qtd = int(it.get("qtitcarrinho") or it.get("qt") or 1)
            vr_unit = float(it.get("vrunitario", 0) or 0)
            dsobsitcar = it.get("dsobsitcar")
            
            #print("ITEM VENDA =", it)

            db.add(
                ItVenda(
                    venda_id=venda_id,
                    produto_id=produto_id,
                    qtitvenda=qtd,
                    vrunititvenda=vr_unit,
                    dsobsitvenda=dsobsitcar,
                    identregaitvenda="NAO",
                    qrtokenitvenda=gerar_token_qr(),
                    dtexpiraitvenda=fim,
                    nmparticipante=it.get("nmparticipante"),
                    cpfparticipante=it.get("cpfparticipante"),
                    lote_id=it.get("lote_id"),
                )
            )

    if venda:
        _sync_itens_venda(venda.venda_id)

        venda.totalvenda = float(total)

        if hasattr(venda, "dsplataforma"):
            venda.dsplataforma = plataforma

        if chave and hasattr(venda, "idempotency_key") and not getattr(venda, "idempotency_key", None):
            venda.idempotency_key = chave

        pag = (
            db.query(PagVenda)
            .filter(
                PagVenda.venda_id == venda.venda_id,
                PagVenda.sitpagvenda == "PENDENTE",
            )
            .order_by(PagVenda.pagvenda_id.desc())
            .first()
        )

        if not pag:
            pag = PagVenda(
                venda_id=venda.venda_id,
                dsmetodopag=metodo_pagamento,
                vrpagvenda=float(total),
                sitpagvenda="PENDENTE",
                reference_id=f"VENDA-{venda.venda_id}",
                provedor="MERCADOPAGO",
            )
            db.add(pag)
            db.flush()
        else:
            pag.dsmetodopag = metodo_pagamento
            pag.vrpagvenda = float(total)

            if not getattr(pag, "reference_id", None):
                pag.reference_id = f"VENDA-{venda.venda_id}"

            if not getattr(pag, "provedor", None):
                pag.provedor = "MERCADOPAGO"

        return {
            "venda_id": int(venda.venda_id),
            "pagvenda_id": int(pag.pagvenda_id),
            "reference_id": pag.reference_id,
        }

    venda = Venda(
        loja_id=loja_id,
        organizacao_id=organizacao_id,
        cliente_id=cliente_id,
        carrinho_id=carrinho_id,
        sitvenda="PENDENTE",
        totalvenda=float(total),
    )

    if hasattr(venda, "dsplataforma"):
        venda.dsplataforma = plataforma

    if chave and hasattr(venda, "idempotency_key"):
        venda.idempotency_key = chave

    db.add(venda)
    db.flush()

    _sync_itens_venda(venda.venda_id)

    reference_id = f"VENDA-{venda.venda_id}"

    pag = PagVenda(
        venda_id=venda.venda_id,
        dsmetodopag=metodo_pagamento,
        vrpagvenda=float(total),
        sitpagvenda="PENDENTE",
        reference_id=reference_id,
        provedor="MERCADOPAGO",
    )

    db.add(pag)
    db.flush()

    return {
        "venda_id": int(venda.venda_id),
        "pagvenda_id": int(pag.pagvenda_id),
        "reference_id": reference_id,
    }