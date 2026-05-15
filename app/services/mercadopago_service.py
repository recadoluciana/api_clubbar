# app/services/mercadopago_service.py
from __future__ import annotations

import os
import uuid
from typing import Any, Dict

import httpx
from fastapi import HTTPException


MERCADOPAGO_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN", "")
MERCADOPAGO_BASE = os.getenv(
    "MERCADOPAGO_BASE",
    "https://api.mercadopago.com",
)
MERCADOPAGO_TIMEOUT = float(os.getenv("MERCADOPAGO_TIMEOUT", "30"))


def _clean_digits(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())


def _headers(idempotency_key: str | None = None) -> Dict[str, str]:
    if not MERCADOPAGO_ACCESS_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="MERCADOPAGO_ACCESS_TOKEN não configurado",
        )

    headers = {
        "Authorization": f"Bearer {MERCADOPAGO_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    if idempotency_key:
        headers["X-Idempotency-Key"] = idempotency_key

    return headers


async def criar_pagamento_pix(
    *,
    valor: float,
    descricao: str,
    email: str,
    nome: str,
    cpf: str | None,
    venda_id: int,
) -> Dict[str, Any]:
    cpf_limpo = _clean_digits(cpf)

    body = {
        "transaction_amount": float(valor),
        "description": descricao,
        "payment_method_id": "pix",
        "external_reference": str(venda_id),
        "payer": {
            "email": email,
            "first_name": nome,
        },
    }

    if cpf_limpo:
        body["payer"]["identification"] = {
            "type": "CPF",
            "number": cpf_limpo,
        }

    idempotency_key = str(uuid.uuid4())

    async with httpx.AsyncClient(timeout=MERCADOPAGO_TIMEOUT) as client:
        response = await client.post(
            f"{MERCADOPAGO_BASE}/v1/payments",
            json=body,
            headers=_headers(idempotency_key),
        )

    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}

    print("[MERCADOPAGO PIX] STATUS =", response.status_code)
    print("[MERCADOPAGO PIX] RESPONSE =", data)

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=data)

    return data


async def consultar_pagamento(
    pagamento_id: str,
) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=MERCADOPAGO_TIMEOUT) as client:
        response = await client.get(
            f"{MERCADOPAGO_BASE}/v1/payments/{pagamento_id}",
            headers=_headers(),
        )

    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}

    print("[MERCADOPAGO CONSULTA] STATUS =", response.status_code)
    print("[MERCADOPAGO CONSULTA] RESPONSE =", data)

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=data)

    return data

@router.post("/mercadopago/consultar/{venda_id}")
async def consultar_mercadopago_por_venda(
    venda_id: int,
    db: Session = Depends(get_db),
):
    pag = (
        db.query(PagVenda)
        .filter(PagVenda.venda_id == venda_id)
        .order_by(PagVenda.pagvenda_id.desc())
        .first()
    )

    if not pag:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    if not pag.idtransacaopagvenda:
        raise HTTPException(status_code=400, detail="ID do pagamento não encontrado")

    data = await consultar_pagamento(str(pag.idtransacaopagvenda))

    status_mp = (data.get("status") or "").lower()

    if status_mp == "approved":
        with db.begin():
            resultado = set_venda_como_paga(
                db,
                venda_id=venda_id,
                gateway="OUTRO",
                payload={
                    "charges": [
                        {
                            "id": str(data.get("id")),
                            "status": "PAID",
                        }
                    ],
                    "mercadopago": data,
                },
            )

        return {
            "ok": True,
            "venda_id": venda_id,
            "status": "PAGO",
            "resultado": resultado,
        }

    return {
        "ok": True,
        "venda_id": venda_id,
        "status": status_mp or "PENDENTE",
    }