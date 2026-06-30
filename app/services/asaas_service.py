#assas_service.py
import os
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.cliente import Cliente
import json

ASAAS_API_KEY = os.getenv("ASAAS_API_KEY")
ASAAS_BASE_URL = os.getenv("ASAAS_BASE_URL", "https://api-sandbox.asaas.com/v3")


def _headers():
    if not ASAAS_API_KEY:
        raise HTTPException(status_code=500, detail="ASAAS_API_KEY não configurada")

    return {
        "Content-Type": "application/json",
        "access_token": ASAAS_API_KEY,
    }


async def obter_ou_criar_customer_asaas(
    db: Session,
    *,
    cliente_id: int,
):
    cliente = (
        db.query(Cliente)
        .filter(Cliente.cliente_id == cliente_id)
        .first()
    )

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    if cliente.idclienteasaas:
        return cliente.idclienteasaas

    body = {
        "name": cliente.nmcliente,
        "cpfCnpj": cliente.nrcpfcliente,
        "email": cliente.emailcliente,
        "mobilePhone": cliente.nrtelcliente,
        "externalReference": str(cliente.cliente_id),
    }

    body = {k: v for k, v in body.items() if v}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{ASAAS_BASE_URL}/customers",
            json=body,
            headers=_headers(),
        )

    data = response.json()

    print("[ASAAS CUSTOMER] STATUS =", response.status_code)
    print("[ASAAS CUSTOMER] RESPONSE =", data)

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)

    customer_id = data.get("id")

    if not customer_id:
        raise HTTPException(
            status_code=500,
            detail="Asaas não retornou o customer_id.",
        )

    cliente.idclienteasaas = customer_id

    db.commit()
    db.refresh(cliente)

    return customer_id

async def criar_cobranca_asaas(
    *,
    customer_id: str,
    valor: float,
    descricao: str,
    external_reference: str,
):
    body = {
        "customer": customer_id,
        "billingType": "UNDEFINED",
        "value": round(float(valor or 0), 2),
        "dueDate": "2026-12-31",
        "description": descricao,
        "externalReference": external_reference,
        "callback": {
            "successUrl": f"https://api.clubbar.com.br/asaas/retorno?carrinho_id={external_reference.replace('CARRINHO-', '')}",
            "autoRedirect": True,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{ASAAS_BASE_URL}/payments",
            json=body,
            headers=_headers(),
        )

    data = response.json()

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)

    return data

import json
import re

import httpx
from fastapi import HTTPException


def somente_numeros(valor: str | None) -> str | None:
    if not valor:
        return None
    numeros = re.sub(r"\D", "", valor)
    return numeros or None


async def criar_checkout_asaas(
    *,
    valor: float,
    descricao: str,
    external_reference: str,
    carrinho_id: int,
    nome_cliente: str | None = None,
    email_cliente: str | None = None,
    cpf_cliente: str | None = None,
    celular_cliente: str | None = None,
):
    nome_limpo = (nome_cliente or "").strip()

    if not nome_limpo:
        nome_limpo = "Cliente Clubbar"

    if len(nome_limpo.split()) < 2:
        nome_limpo = f"{nome_limpo} Clubbar"

    cpf_limpo = somente_numeros(cpf_cliente)
    celular_limpo = somente_numeros(celular_cliente)

    customer_data = {
        "name": nome_limpo,
        "email": email_cliente,
        "cpfCnpj": cpf_limpo,
        "phone": celular_limpo,

        # obrigatório no checkout Asaas quando usa customerData
        "address": "Rua Mourato Coelho",
        "addressNumber": "629",
        "postalCode": "05417001",
        "province": "Pinheiros",
    }

    customer_data = {
        k: v
        for k, v in customer_data.items()
        if v is not None and str(v).strip() != ""
    }

    url_retorno = (
        f"https://api.clubbar.com.br/asaas/retorno"
        f"?carrinho_id={carrinho_id}"
    )

    body = {
        "billingTypes": ["PIX", "CREDIT_CARD"],
        "chargeTypes": ["DETACHED"],
        "minutesToExpire": 60,
        "externalReference": external_reference,
        "callback": {
            "successUrl": url_retorno,
            "cancelUrl": url_retorno,
            "expiredUrl": url_retorno,
        },
        "items": [
            {
                "externalReference": external_reference,
                "name": "Compra Clubbar",
                "description": descricao,
                "quantity": 1,
                "value": round(float(valor), 2),
            }
        ],
        "customerData": customer_data,
    }

    print("=" * 80)
    print("[ASAAS CHECKOUT REQUEST]")
    print(json.dumps(body, indent=2, ensure_ascii=False))

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{ASAAS_BASE_URL}/checkouts",
                json=body,
                headers=_headers(),
            )

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        print("[ASAAS CHECKOUT RESPONSE]")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        print("=" * 80)

        if response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=data,
            )

        checkout_id = data.get("id")
        checkout_link = data.get("link")

        if not checkout_id or not checkout_link:
            raise HTTPException(
                status_code=500,
                detail={
                    "erro": "Checkout Asaas criado sem id ou link.",
                    "asaas_response": data,
                },
            )

        return {
            "id": checkout_id,
            "link": checkout_link,
            "status": data.get("status"),
            "externalReference": data.get("externalReference"),
            "raw": data,
        }

    except HTTPException:
        raise

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Timeout ao criar checkout no Asaas.",
        )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Erro de conexão com Asaas: {str(e)}",
        )

async def criar_cobranca_pix_asaas(
    *,
    customer_id: str,
    valor: float,
    descricao: str,
    external_reference: str,
):
    body = {
        "customer": customer_id,
        "billingType": "PIX",
        "value": round(float(valor or 0), 2),
        "dueDate": "2026-12-31",
        "description": descricao,
        "externalReference": external_reference,
        "callback": {
            "successUrl": "https://api.clubbar.com.br/asaas/sucesso",
            "autoRedirect": True,
        },
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{ASAAS_BASE_URL}/payments",
            json=body,
            headers=_headers(),
        )

    data = response.json()

    print("[ASAAS PIX] STATUS =", response.status_code)
    print("[ASAAS PIX] RESPONSE =", data)

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)

    return data


async def buscar_qrcode_pix_asaas(payment_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{ASAAS_BASE_URL}/payments/{payment_id}/pixQrCode",
            headers=_headers(),
        )

    data = response.json()

    print("[ASAAS PIX QR] STATUS =", response.status_code)
    print("[ASAAS PIX QR] RESPONSE =", data)

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)

    return data