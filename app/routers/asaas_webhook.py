from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db

from app.services.venda_gateway_service import criar_venda_paga_por_carrinho_gateway

router = APIRouter(
    prefix="/asaas",
    tags=["Asaas"],
)

@router.post("/webhook")
async def asaas_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        body = await request.json()
    except Exception:
        body = {}

    print("[ASAAS WEBHOOK]")
    print(body)

    evento = body.get("event")
    payment = body.get("payment") or {}

    status = (payment.get("status") or "").upper()
    external_reference = str(payment.get("externalReference") or "").strip()

    if not external_reference.startswith("CARRINHO-"):
        return {"ok": True, "ignored": True, "msg": "externalReference ignorado"}

    carrinho_id = int(external_reference.replace("CARRINHO-", "").split("-")[0])

    if evento not in ["PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"] and status not in ["RECEIVED", "CONFIRMED"]:
        return {
            "ok": True,
            "ignored": True,
            "event": evento,
            "status": status,
            "carrinho_id": carrinho_id,
        }

    resultado = await criar_venda_paga_por_carrinho_gateway(
        db,
        carrinho_id=carrinho_id,
        gateway="ASAAS",
        pagamento=payment,
        metodo_pagamento="CREDITO",
    )

    db.commit()

    return {
        "ok": True,
        "gateway": "ASAAS",
        "event": evento,
        "status": status,
        "carrinho_id": carrinho_id,
        "resultado": resultado,
    }