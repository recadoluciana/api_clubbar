# app/services/mercadopago_service.py
from __future__ import annotations

import os
import uuid
import asyncio
from typing import Any, Dict

import httpx
from fastapi import HTTPException

MERCADOPAGO_NOTIFICATION_URL = os.getenv("MERCADOPAGO_NOTIFICATION_URL")

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
    external_reference: str | None = None,
) -> Dict[str, Any]:
    cpf_limpo = _clean_digits(cpf)

    valor = round(float(valor or 0), 2)

    if valor <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Valor PIX inválido: {valor}",
        )

    email = (email or "").strip()
    nome = (nome or "").strip()

    if not email or "@" not in email:
        email = "cliente@clubbar.com.br"

    if not nome:
        nome = "Cliente"

    partes_nome = nome.strip().split()

    if len(partes_nome) > 1:
        first_name = partes_nome[0]
        last_name = " ".join(partes_nome[1:])
    else:
        first_name = nome.strip()
        last_name = "-" 
           
    email_pix = email

    if MERCADOPAGO_ACCESS_TOKEN.startswith("TEST-"):
        email_pix = "test_user_123@testuser.com"

    body = {
        "transaction_amount": valor,

        "description": descricao or f"Compra Clubbar #{venda_id}",

        "payment_method_id": "pix",

        # importante para o webhook localizar a venda
        "external_reference": external_reference or str(venda_id),

        # webhook do Mercado Pago
        "notification_url": MERCADOPAGO_NOTIFICATION_URL,

        # informações adicionais para aumentar aprovação e rastreabilidade
        "metadata": {
            "venda_id": venda_id,
            "tipo_pagamento": "PIX",
        },

        "additional_info": {
            "items": [
                {
                    "id": str(venda_id),
                    "title": descricao or f"Compra Clubbar #{venda_id}",
                    "description": descricao or f"Compra Clubbar #{venda_id}",
                    "quantity": 1,
                    "unit_price": valor,
                }
            ]
        },

        "payer": {
            "email": email_pix,
            "first_name": first_name,
            "last_name": last_name,
        },
    }

    if cpf_limpo and len(cpf_limpo) == 11:
        body["payer"]["identification"] = {
            "type": "CPF",
            "number": cpf_limpo,
        }

    print("[PIX] BODY =", body)

    last_data: Dict[str, Any] = {}

    for tentativa in range(1, 4):
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

        last_data = data

        print("[MERCADOPAGO PIX] TENTATIVA =", tentativa)
        print("[MERCADOPAGO PIX] STATUS =", response.status_code)
        print("[MERCADOPAGO PIX] RESPONSE =", data)

        if response.status_code < 400:
            return data

        await asyncio.sleep(1)

    raise HTTPException(status_code=502, detail=last_data)


async def criar_pagamento_cartao_mp(
    *,
    valor: float,
    descricao: str,
    email: str | None,
    nome: str | None,
    cpf: str | None,
    external_reference: str,
    card_token: str,
    payment_method_id: str | None,
    issuer_id: str | None,
    installments: int,
    tipo_pagamento: str,
    idempotency_key: str,
    device_id: str | None = None,
) -> Dict[str, Any]:

    cpf_limpo = _clean_digits(cpf)

    valor = round(float(valor or 0), 2)

    if valor <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"Valor cartão inválido: {valor}",
        )

    if not card_token:
        raise HTTPException(
            status_code=400,
            detail="Token do cartão não informado",
        )

    email = (email or "").strip()
    nome = (nome or "").strip()

    if not email or "@" not in email:
        email = "cliente@clubbar.com.br"

    if not nome:
        nome = "Cliente"

    partes_nome = nome.strip().split()

    if len(partes_nome) > 1:
        first_name = partes_nome[0]
        last_name = " ".join(partes_nome[1:])
    else:
        first_name = nome.strip()
        last_name = "-"    

    payer: Dict[str, Any] = {
        "email": email,
        "first_name": first_name,
        "last_name": last_name,
    }

    if cpf_limpo and len(cpf_limpo) == 11:
        payer["identification"] = {
            "type": "CPF",
            "number": cpf_limpo,
        }

    body: Dict[str, Any] = {
        "transaction_amount": valor,
        "token": card_token,
        "description": descricao or f"Compra Clubbar #{external_reference}",
        "installments": installments or 1,
        "payment_method_id": payment_method_id,
        "payer": payer,
        "external_reference": str(external_reference),
        "notification_url": MERCADOPAGO_NOTIFICATION_URL,
        "metadata": {
            "external_reference": str(external_reference),
            "tipo_pagamento": tipo_pagamento,
        },
        "additional_info": {
            "items": [
                {
                    "id": str(external_reference),
                    "title": descricao or f"Compra Clubbar #{external_reference}",
                    "description": descricao or f"Compra Clubbar #{external_reference}",
                    "quantity": 1,
                    "unit_price": valor,
                }
            ]
        },
    }

    print("[CARTAO] DEVICE_ID =", device_id)


    if issuer_id:
        body["issuer_id"] = issuer_id

    print("[CARTAO] BODY =", body)

    last_data: Dict[str, Any] = {}

    for tentativa in range(1, 4):
        chave = idempotency_key or str(uuid.uuid4())

        headers = {
            **_headers(chave),
            **({"X-meli-session-id": device_id} if device_id else {}),
        }

        print("[CARTAO] HEADERS TEM DEVICE =", "X-meli-session-id" in headers)

        async with httpx.AsyncClient(timeout=MERCADOPAGO_TIMEOUT) as client:
            response = await client.post(
                f"{MERCADOPAGO_BASE}/v1/payments",
                json=body,
                headers=headers,
            )

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        last_data = data

        print("[MERCADOPAGO CARTAO] TENTATIVA =", tentativa)
        print("[MERCADOPAGO CARTAO] STATUS =", response.status_code)
        print("[MERCADOPAGO CARTAO] RESPONSE =", data)

        if response.status_code < 400:
            return data

        await asyncio.sleep(1)

    raise HTTPException(status_code=502, detail=last_data)


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