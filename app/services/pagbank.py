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


# app/services/pagbank.py
async def criar_checkout_externo(
    *,
    reference_id: str,
    items: List[Dict[str, Any]],
    redirect_url: Optional[str],
    notification_urls: List[str],
    payment_notification_urls: Optional[List[str]] = None,
    # novos controles:
    aceitar_cartao: bool = True,
    aceitar_pix: bool = True,
) -> Dict[str, Any]:

    payload: Dict[str, Any] = {
        "reference_id": reference_id,
        "items": items,
        "notification_urls": notification_urls,
    }

    if payment_notification_urls:
        payload["payment_notification_urls"] = payment_notification_urls

    if redirect_url:
        payload["redirect_url"] = redirect_url

    # --- ✅ métodos permitidos ---
    payment_methods = []
    if aceitar_pix:
        payment_methods.append({"type": "PIX"})
    if aceitar_cartao:
        payment_methods.append({"type": "CREDIT_CARD"})

        # --- ✅ trava parcelamento no cartão ---
        payload["payment_methods_configs"] = [
            {
                "type": "CREDIT_CARD",
                "config_options": [
                    {"option": "INSTALLMENTS_LIMIT", "value": "1"},
                ],
            }
        ]

    if not payment_methods:
        raise RuntimeError("Selecione pelo menos um método: PIX e/ou CARTÃO")
        
    if payment_methods:
        payload["payment_methods"] = payment_methods

    async with httpx.AsyncClient(timeout=25) as client:

        print("PAGBANK_ENV:", PAGBANK_ENV)

        url = f"{pagbank_base_url()}/checkouts"
        
        print("PAGBANK URL:", url)

        # aqui é chamado a página do pagbank
        resp = await client.post(
            url,
            headers=_headers(),
            json=payload,
        )
        
        print("\n========= PAGBANK DEBUG =========")
        print("STATUS:", resp.status_code)
        print("RESPONSE TEXT:", resp.text)
        print("REQUEST PAYLOAD:", payload)
        print("=================================\n")

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
