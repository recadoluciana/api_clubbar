# app/services/pagbank.py
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

PAGBANK_TOKEN = os.getenv("PAGBANK_TOKEN", "").strip()
PAGBANK_ENV = os.getenv("PAGBANK_ENV", "sandbox").strip().lower()


def pagbank_base_url() -> str:
    # Sandbox: https://sandbox.api.pagseguro.com/ | Produção: https://api.pagseguro.com :contentReference[oaicite:3]{index=3}
    if PAGBANK_ENV in ("prod", "production"):
        return "https://api.pagseguro.com"
    return "https://sandbox.api.pagseguro.com"


def _headers() -> Dict[str, str]:
    if not PAGBANK_TOKEN:
        raise RuntimeError("PAGBANK_TOKEN não configurado no .env")
    return {
        "Authorization": f"Bearer {PAGBANK_TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


async def criar_checkout_externo(
    *,
    reference_id: str,
    items: List[Dict[str, Any]],
    redirect_url: Optional[str],
    notification_urls: List[str],
    payment_notification_urls: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Cria checkout e retorna {checkout_id, pay_url, raw}
    Endpoint: POST {base}/checkouts :contentReference[oaicite:4]{index=4}
    PAY URL: vem em links[] com rel=PAY :contentReference[oaicite:5]{index=5}
    Webhook: notification_urls / payment_notification_urls :contentReference[oaicite:6]{index=6}
    """
    payload: Dict[str, Any] = {
        "reference_id": reference_id,
        "items": items,
        "notification_urls": notification_urls,  # webhook do checkout :contentReference[oaicite:7]{index=7}
    }

    if payment_notification_urls:
        payload["payment_notification_urls"] = payment_notification_urls  # webhook do pagamento :contentReference[oaicite:8]{index=8}

    if redirect_url:
        payload["redirect_url"] = redirect_url

    async with httpx.AsyncClient(timeout=25) as client:
        resp = await client.post(
            f"{pagbank_base_url()}/checkouts",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()

    checkout_id = data.get("id")
    pay_url = None
    for link in data.get("links", []):
        if link.get("rel") == "PAY":
            pay_url = link.get("href")
            break

    if not pay_url:
        raise RuntimeError("PagBank não retornou link PAY em links[].rel=PAY")  # :contentReference[oaicite:9]{index=9}

    return {"checkout_id": checkout_id, "pay_url": pay_url, "raw": data}
