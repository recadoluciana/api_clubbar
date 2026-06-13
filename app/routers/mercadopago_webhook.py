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

        pagamento_id = (
            data.get("id")
            or body.get("id")
        )

        if pagamento_id:
            pagamento_id = str(pagamento_id).strip()

        if not pagamento_id:
            return {
                "ok": True,
                "mensagem": "Webhook sem payment id",
            }

        print("[MP WEBHOOK] pagamento_id =", pagamento_id)
        
        try:

            pagamento = await consultar_pagamento(str(pagamento_id))

        except Exception as e:

            print("[MP WEBHOOK] pagamento ainda indisponível")

            return {
                "ok": True,
                "mensagem": "Pagamento ainda não disponível",
            }

        print("[MP WEBHOOK] pagamento =", pagamento)

        external_reference = pagamento.get("external_reference")

        if not external_reference or not str(external_reference).isdigit():
            print("[MP WEBHOOK] external_reference inválido:", external_reference)
            return {"ok": True, "msg": "external_reference ignorado"}

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

        elif status_mp in {"cancelled", "rejected"}:

            with db.begin():
                set_venda_como_cancelada(
                    db,
                    venda_id=venda_id,
                    gateway="MERCADOPAGO",
                    payload=pagamento,
                    fechar_carrinho=False,
                )

        elif status_mp in {"pending", "in_process", "authorized"}:
            # Apenas registra e aguarda nova notificação
            print(f"[MP WEBHOOK] Pagamento em processamento: {status_mp}")

        elif status_mp in {"refunded", "charged_back"}:
            print(f"[MP WEBHOOK] Pagamento estornado/chargeback: {status_mp}")
            # Futuramente implementar lógica de reversão

        else:
            print(f"[MP WEBHOOK] Status não tratado: {status_mp}")

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