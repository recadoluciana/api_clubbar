#assas_service.py
import os
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.cliente import Cliente

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