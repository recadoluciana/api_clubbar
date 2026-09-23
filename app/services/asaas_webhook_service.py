import os

import httpx
from fastapi import HTTPException

from app.core.config import ASAAS_WEBHOOK_TOKEN, PUBLIC_API_BASE_URL


ASAAS_BASE_URL = os.getenv(
    "ASAAS_BASE_URL", "https://api-sandbox.asaas.com/v3"
).rstrip("/")
_EVENTOS_PAGAMENTO = ["PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"]


def _detalhe_erro(response: httpx.Response) -> str:
    try:
        dados = response.json()
    except ValueError:
        return "Erro ao configurar a confirmação automática de pagamentos."
    erros = dados.get("errors") if isinstance(dados, dict) else None
    if isinstance(erros, list):
        mensagens = [
            str(item.get("description") or item.get("message") or "").strip()
            for item in erros
            if isinstance(item, dict)
        ]
        if any(mensagens):
            return " ".join(item for item in mensagens if item)
    if isinstance(dados, dict):
        return str(dados.get("message") or "").strip() or (
            "Erro ao configurar a confirmação automática de pagamentos."
        )
    return "Erro ao configurar a confirmação automática de pagamentos."


async def garantir_webhook_pagamentos_asaas(api_key: str) -> None:
    """Garante que pagamentos da subconta retornem ao Clubbar automaticamente."""
    base_api = PUBLIC_API_BASE_URL.strip().rstrip("/")
    url_api = f"{base_api}/asaas/webhook"
    token = ASAAS_WEBHOOK_TOKEN.strip()
    if not base_api or not token or len(token) < 32:
        raise HTTPException(
            status_code=503,
            detail=(
                "A confirmação automática de pagamentos não está configurada. "
                "Configure a URL pública da API e o token de webhook do Asaas."
            ),
        )

    headers = {"accept": "application/json", "access_token": api_key}
    configuracao = {
        "name": "Clubbar - confirmação de pagamentos",
        "url": url_api,
        "enabled": True,
        "interrupted": False,
        "apiVersion": 3,
        "authToken": token,
        "sendType": "SEQUENTIALLY",
        "events": _EVENTOS_PAGAMENTO,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resposta_lista = await client.get(
            f"{ASAAS_BASE_URL}/webhooks",
            headers=headers,
            params={"limit": 100},
        )
        if resposta_lista.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=_detalhe_erro(resposta_lista),
            )
        existentes = resposta_lista.json().get("data") or []
        existente = next(
            (
                item
                for item in existentes
                if str(item.get("url") or "").rstrip("/") == url_api
            ),
            None,
        )

        if existente and existente.get("id"):
            resposta = await client.put(
                f"{ASAAS_BASE_URL}/webhooks/{existente['id']}",
                headers=headers,
                json=configuracao,
            )
        else:
            resposta_conta = await client.get(
                f"{ASAAS_BASE_URL}/myAccount",
                headers=headers,
            )
            if resposta_conta.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=_detalhe_erro(resposta_conta),
                )
            email = str(resposta_conta.json().get("email") or "").strip()
            if not email:
                raise HTTPException(
                    status_code=502,
                    detail="A subconta Asaas não possui e-mail para configurar o webhook.",
                )
            resposta = await client.post(
                f"{ASAAS_BASE_URL}/webhooks",
                headers=headers,
                json={**configuracao, "email": email},
            )

    if resposta.status_code >= 400:
        raise HTTPException(status_code=502, detail=_detalhe_erro(resposta))
