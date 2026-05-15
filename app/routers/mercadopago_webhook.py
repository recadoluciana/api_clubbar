# app/routers/mercadopago_webhook.py
from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.pagvenda import PagVenda
from app.services.mercadopago_service import consultar_pagamento
from app.services.pagamento_status_service import (
    set_venda_como_paga,
    set_venda_como_cancelada,
)

router = APIRouter(prefix="/mercadopago", tags=["Mercado Pago"])


@router.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        body = await request.json()
        print("[MERCADOPAGO WEBHOOK] BODY =", body)

        tipo = body.get("type") or body.get("topic")
        data = body.get("data") or {}
        pagamento_id = data.get("id") or body.get("id")

        if not pagamento_id:
            return {"ok": True, "mensagem": "Webhook sem payment id"}

        pagamento = await consultar_pagamento(str(pagamento_id))

        external_reference = pagamento.get("external_reference")

        if not external_reference:
            return {
                "ok": True,
                "mensagem": "Pagamento sem external_reference",
                "pagamento_id": pagamento_id,
            }

        venda_id = int(external_reference)

        status_mp = (pagamento.get("status") or "").lower()

        print("[MERCADOPAGO WEBHOOK] venda_id =", venda_id)
        print("[MERCADOPAGO WEBHOOK] status =", status_mp)

        if status_mp == "approved":
            with db.begin():
                set_venda_como_paga(
                    db,
                    venda_id=venda_id,
                    gateway="OUTRO",
                    payload={
                        "id": pagamento.get("id"),
                        "status": "PAID",
                        "charges": [
                            {
                                "id": str(pagamento.get("id")),
                                "status": "PAID",
                            }
                        ],
                        "mercadopago": pagamento,
                    },
                )

        elif status_mp in {"cancelled", "rejected"}:
            with db.begin():
                set_venda_como_cancelada(
                    db,
                    venda_id=venda_id,
                    gateway="OUTRO",
                    payload={
                        "id": pagamento.get("id"),
                        "status": "CANCELLED",
                        "charges": [
                            {
                                "id": str(pagamento.get("id")),
                                "status": "CANCELLED",
                            }
                        ],
                        "mercadopago": pagamento,
                    },
                )

        return {
            "ok": True,
            "tipo": tipo,
            "pagamento_id": pagamento_id,
            "venda_id": venda_id,
            "status": status_mp,
        }

    except Exception as e:
        print("[MERCADOPAGO WEBHOOK][ERRO]", repr(e))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))