from __future__ import annotations

import os
import traceback
from contextlib import nullcontext

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.venda_gateway_service import criar_venda_paga_por_carrinho_gateway

router = APIRouter(
    prefix="/stripe",
    tags=["Stripe"],
)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


def db_tx(db: Session):
    return nullcontext() if db.in_transaction() else db.begin()


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        if STRIPE_WEBHOOK_SECRET:
            try:
                event = stripe.Webhook.construct_event(
                    payload=payload,
                    sig_header=sig_header,
                    secret=STRIPE_WEBHOOK_SECRET,
                )
            except Exception as e:
                print("[STRIPE WEBHOOK] assinatura inválida:", repr(e))
                raise HTTPException(status_code=400, detail="Assinatura inválida")
        else:
            event = stripe.Event.construct_from(
                await request.json(),
                stripe.api_key,
            )

        print("[STRIPE WEBHOOK] EVENT =", event.get("type"))

        if event.get("type") != "checkout.session.completed":
            return {
                "ok": True,
                "ignored": True,
                "type": event.get("type"),
            }

        session = event["data"]["object"]

        metadata = session.get("metadata") or {}
        carrinho_id = int(metadata.get("carrinho_id") or 0)

        if carrinho_id <= 0:
            return {
                "ok": True,
                "msg": "Webhook sem carrinho_id",
                "session_id": session.get("id"),
            }

        pagamento = {
            "id": session.get("id"),
            "payment_intent": session.get("payment_intent"),
            "status": session.get("payment_status"),
            "amount_total": session.get("amount_total"),
            "currency": session.get("currency"),
            "metadata": metadata,
            "stripe_session": dict(session),
        }

        resultado = None

        if session.get("payment_status") == "paid":
            with db_tx(db):
                resultado = await criar_venda_paga_por_carrinho_gateway(
                    db,
                    carrinho_id=carrinho_id,
                    gateway="STRIPE",
                    pagamento=pagamento,
                    metodo_pagamento="CREDITO",
                )

        return {
            "ok": True,
            "gateway": "STRIPE",
            "session_id": session.get("id"),
            "payment_status": session.get("payment_status"),
            "carrinho_id": carrinho_id,
            "resultado": resultado,
        }

    except HTTPException:
        raise

    except Exception as e:
        print("[STRIPE WEBHOOK][ERRO]", repr(e))
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )