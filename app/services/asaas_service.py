#assas_service.py
import os
import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.cliente import Cliente
from app.models.clienteasaas import ClienteAsaas
import json

import re
import uuid

from app.core.config import APP_ENV, PUBLIC_API_BASE_URL
ASAAS_BASE_URL = os.getenv("ASAAS_BASE_URL", "https://api-sandbox.asaas.com/v3")


def criar_referencia_checkout_asaas(carrinho_id: int) -> str:
    ambiente = re.sub(r"[^a-z0-9_-]", "-", APP_ENV.lower()).strip("-") or "unknown"
    identificador = uuid.uuid4().hex[:12]
    return f"CLUBBAR-{ambiente}-CARRINHO-{int(carrinho_id)}-{identificador}"


def _url_api_publica() -> str:
    if not PUBLIC_API_BASE_URL:
        raise HTTPException(
            status_code=500,
            detail="PUBLIC_API_BASE_URL não configurada",
        )
    return PUBLIC_API_BASE_URL
def _headers(api_key: str):
    if not api_key:
        raise HTTPException(status_code=503, detail="Conta Asaas da loja sem API Key")
    return {
        "Content-Type": "application/json",
        "access_token": api_key,
    }


async def sincronizar_cliente_com_asaas_se_precisar(
    db: Session,
    *,
    cliente_id: int,
    loja_id: int,
    api_key: str,
):
    cliente = (
        db.query(Cliente)
        .filter(Cliente.cliente_id == cliente_id)
        .first()
    )

    vinculo = db.query(ClienteAsaas).filter(
        ClienteAsaas.cliente_id == cliente_id,
        ClienteAsaas.loja_id == loja_id,
    ).first()

    if not cliente or not vinculo:
        return

    ja_tem_endereco = all([
        cliente.endcliente,
        cliente.nrendcliente,
        cliente.bairrocliente,
        cliente.cepcliente,
    ])

    if ja_tem_endereco:
        return

    customer = await buscar_customer_asaas(vinculo.asaas_customer_id, api_key)

    cliente.endcliente = customer.get("address") or cliente.endcliente
    cliente.nrendcliente = customer.get("addressNumber") or cliente.nrendcliente
    cliente.complcliente = customer.get("complement") or cliente.complcliente
    cliente.bairrocliente = customer.get("province") or cliente.bairrocliente
    cliente.cepcliente = customer.get("postalCode") or cliente.cepcliente
    cliente.cidadecliente = customer.get("city") or cliente.cidadecliente
    cliente.ufcliente = customer.get("state") or cliente.ufcliente

    cliente.nrtelcliente = (
        customer.get("mobilePhone")
        or customer.get("phone")
        or cliente.nrtelcliente
    )


async def buscar_customer_asaas(customer_id: str, api_key: str):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{ASAAS_BASE_URL}/customers/{customer_id}",
            headers=_headers(api_key),
        )

    data = response.json()

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)

    return data

async def obter_ou_criar_customer_asaas(
    db: Session,
    *,
    cliente_id: int,
    loja_id: int,
    api_key: str,
):
    cliente = (
        db.query(Cliente)
        .filter(Cliente.cliente_id == cliente_id)
        .first()
    )

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    body = {
        "name": cliente.nmcliente,
        "cpfCnpj": cliente.nrcpfcliente,
        "email": cliente.emailcliente,
        "mobilePhone": cliente.nrtelcliente,
        "phone": cliente.nrtelcliente,
        "address": cliente.endcliente,
        "addressNumber": cliente.nrendcliente,
        "complement": cliente.complcliente,
        "province": cliente.bairrocliente,
        "postalCode": cliente.cepcliente,
        "externalReference": str(cliente.cliente_id),
    }

    body = {k: v for k, v in body.items() if v}

    vinculo = db.query(ClienteAsaas).filter(
        ClienteAsaas.cliente_id == cliente_id,
        ClienteAsaas.loja_id == loja_id,
    ).first()

    if vinculo:
        customer_id = vinculo.asaas_customer_id

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{ASAAS_BASE_URL}/customers/{customer_id}",
                json=body,
                headers=_headers(api_key),
            )

        data = response.json()

        print("[ASAAS CUSTOMER UPDATE] STATUS =", response.status_code)
        print("[ASAAS CUSTOMER UPDATE] RESPONSE =", data)

        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=data)

        return customer_id

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{ASAAS_BASE_URL}/customers",
            json=body,
            headers=_headers(api_key),
        )

    data = response.json()

    print("[ASAAS CUSTOMER CREATE] STATUS =", response.status_code)
    print("[ASAAS CUSTOMER CREATE] RESPONSE =", data)

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)

    customer_id = data.get("id")

    if not customer_id:
        raise HTTPException(
            status_code=500,
            detail="Asaas não retornou o customer_id.",
        )

    db.add(ClienteAsaas(
        cliente_id=cliente_id,
        loja_id=loja_id,
        asaas_customer_id=customer_id,
    ))
    db.commit()

    return customer_id

async def sincronizar_cliente_com_asaas(
    db: Session,
    *,
    cliente_id: int,
    loja_id: int,
    api_key: str,
):
    cliente = (
        db.query(Cliente)
        .filter(Cliente.cliente_id == cliente_id)
        .first()
    )

    if not cliente:
        return

    vinculo = db.query(ClienteAsaas).filter(
        ClienteAsaas.cliente_id == cliente_id,
        ClienteAsaas.loja_id == loja_id,
    ).first()
    if not vinculo:
        return

    customer = await buscar_customer_asaas(vinculo.asaas_customer_id, api_key)

    cliente.nmcliente = customer.get("name") or cliente.nmcliente
    cliente.emailcliente = customer.get("email") or cliente.emailcliente

    cliente.nrtelcliente = (
        customer.get("mobilePhone")
        or customer.get("phone")
        or cliente.nrtelcliente
    )

    cliente.nrcpfcliente = (
        customer.get("cpfCnpj")
        or cliente.nrcpfcliente
    )

    cliente.endcliente = (
        customer.get("address")
        or cliente.endcliente
    )

    cliente.nrendcliente = (
        customer.get("addressNumber")
        or cliente.nrendcliente
    )

    cliente.complcliente = (
        customer.get("complement")
        or cliente.complcliente
    )

    cliente.bairrocliente = (
        customer.get("province")
        or cliente.bairrocliente
    )

    cliente.cepcliente = (
        customer.get("postalCode")
        or cliente.cepcliente
    )

    cliente.cidadecliente = (
        customer.get("city")
        or cliente.cidadecliente
    )

    cliente.ufcliente = (
        customer.get("state")
        or cliente.ufcliente
    )

    db.commit()
    db.refresh(cliente)


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
    api_key: str,
    splits: list[dict] | None = None,
    nome_cliente: str | None = None,
    email_cliente: str | None = None,
    cpf_cliente: str | None = None,
    celular_cliente: str | None = None,
    endcliente: str | None = None,
    nrendcliente: str | None = None,
    complcliente: str | None = None,
    bairrocliente: str | None = None,
    cepcliente: str | None = None,
    items: list[dict] | None = None,
):
    nome_limpo = (nome_cliente or "").strip()

    if not nome_limpo:
        nome_limpo = "Cliente Clubbar"

    if len(nome_limpo.split()) < 2:
        nome_limpo = f"{nome_limpo} Clubbar"

    cpf_limpo = somente_numeros(cpf_cliente)
    
    telefone_limpo = "".join(filter(str.isdigit, celular_cliente or ""))
    cep_limpo = "".join(filter(str.isdigit, cepcliente or ""))

    tem_customer_data_completo = all([
        nome_limpo,
        email_cliente,
        cpf_limpo,
        telefone_limpo and len(telefone_limpo) >= 10,
        endcliente and endcliente.strip(),
        nrendcliente and nrendcliente.strip(),
        bairrocliente and bairrocliente.strip(),
        cep_limpo and len(cep_limpo) == 8,
    ])

    url_api_publica = _url_api_publica()

    items_asaas = items if items else [
        {
            "externalReference": external_reference,
            "name": "Compra Clubbar",
            "description": descricao,
            "quantity": 1,
            "value": round(float(valor), 2),
        }
    ]
    
    body = {
        "billingTypes": ["PIX", "CREDIT_CARD"],
        "chargeTypes": ["DETACHED"],
        "minutesToExpire": 10,
        "externalReference": external_reference,
        "callback": {
            "successUrl": f"{url_api_publica}/asaas/retorno?carrinho_id={carrinho_id}&acao=sucesso",
            "cancelUrl": f"{url_api_publica}/asaas/retorno?carrinho_id={carrinho_id}&acao=cancelado",
            "expiredUrl": f"{url_api_publica}/asaas/retorno?carrinho_id={carrinho_id}&acao=expirado",
        },
        "items": items_asaas,
    }

    if splits:
        body["splits"] = splits

    if tem_customer_data_completo:
        body["customerData"] = {
            "name": nome_limpo,
            "email": email_cliente,
            "cpfCnpj": cpf_limpo,
            "mobilePhone": telefone_limpo,
            "address": endcliente,
            "addressNumber": nrendcliente,
            "complement": complcliente or "",
            "province": bairrocliente,
            "postalCode": cep_limpo,
        }

    print("=" * 80)
    print("[ASAAS CHECKOUT REQUEST]")
    print(json.dumps(body, indent=2, ensure_ascii=False))
    print("[ASAAS ITEMS]")
    print(json.dumps(items_asaas, indent=2, ensure_ascii=False))

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{ASAAS_BASE_URL}/checkouts",
                json=body,
                headers=_headers(api_key),
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


async def buscar_qrcode_pix_asaas(payment_id: str, api_key: str):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{ASAAS_BASE_URL}/payments/{payment_id}/pixQrCode",
            headers=_headers(api_key),
        )

    data = response.json()

    print("[ASAAS PIX QR] STATUS =", response.status_code)
    print("[ASAAS PIX QR] RESPONSE =", data)

    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=data)

    return data
