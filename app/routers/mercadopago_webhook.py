# app/routers/mercadopago_webhook.py

from __future__ import annotations

import traceback

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db

from app.services.mercadopago_service import consultar_pagamento

from app.services.pagamento_status_service import (
    set_venda_como_paga,
    set_venda_como_cancelada,
)

router = APIRouter(
    prefix="/mercadopago",
    tags=["Mercado Pago"],
)


@router.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:

        body = await request.json()

        print("[MP WEBHOOK] BODY =", body)

        tipo = body.get("type") or body.get("topic")

        data = body.get("data") or {}

        pagamento_id = data.get("id")

        if not pagamento_id:
            return {
                "ok": True,
                "mensagem": "Webhook sem payment id",
            }

        pagamento = await consultar_pagamento(str(pagamento_id))

        print("[MP WEBHOOK] pagamento =", pagamento)

        external_reference = pagamento.get("external_reference")

        if not external_reference:
            return {
                "ok": True,
                "mensagem": "Pagamento sem external_reference",
            }

        venda_id = int(external_reference)

        status_mp = (pagamento.get("status") or "").lower()

        print("[MP WEBHOOK] venda_id =", venda_id)
        print("[MP WEBHOOK] status =", status_mp)

        # approved
        if status_mp == "approved":

            with db.begin():

                set_venda_como_paga(
                    db,
                    venda_id=venda_id,
                    gateway="MERCADOPAGO",
                    payload=pagamento,
                )

        # cancelado / rejeitado
        elif status_mp in {"cancelled", "rejected"}:

            with db.begin():

                set_venda_como_cancelada(
                    db,
                    venda_id=venda_id,
                    gateway="MERCADOPAGO",
                    payload=pagamento,
                )

        return {
            "ok": True,
            "venda_id": venda_id,
            "status": status_mp,
            "pagamento_id": pagamento_id,
            "tipo": tipo,
        }

    except HTTPException:
        raise

    except Exception as e:

        print("[MP WEBHOOK][ERRO]", repr(e))
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )