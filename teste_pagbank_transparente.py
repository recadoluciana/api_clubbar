# teste_pagbank_transparente.py
import asyncio  # <-- Adicione esta linha no topo
import os
import json
import httpx
import time

TOKEN = "7b8da97f-3aaf-4fc8-80ed-79f180630ee3a2054d9341daa4402117dff6a1bd0d20d5ef-2567-41a7-bc9b-be0896a82b23"
BASE  = "https://sandbox.api.pagseguro.com"

def headers():
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

async def criar_e_pagar(encrypted_card: str):
    payload = {
        "reference_id": f"PEDIDO_{int(time.time())}",
        "customer": {
            "name": "Jose da Silva",
            "email": "cliente@gmail.com",
            "tax_id": "12345678909",
            "phones": [
                {"country": "55", "area": "11", "number": "999999999", "type": "MOBILE"}
            ],
        },
        "items": [
            {"reference_id": "item-1", "name": "Coxinha", "quantity": 1, "unit_amount": 500}
        ],
        "notification_urls": ["https://example.com/notifica"],
        "charges": [
            {
                "reference_id": f"PAGAMENTO_{int(time.time())}",
                "description": "Compra Clubbar",
                "amount": {"value": 1000, "currency": "BRL"},
                "payment_method": {
                    "type": "CREDIT_CARD",
                    "installments": 1,     # ✅ SEM parcelamento (1x)
                    "capture": True,
                    "card": {"encrypted": encrypted_card, "store": False},
                    "holder": {"name": "Jose da Silva", "tax_id": "12345678909"},
                },
            }
        ],
    }

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{BASE}/orders", headers=headers(), json=payload)

        print("STATUS:", r.status_code)
        print("BODY:", r.text)
        if r.status_code >= 400:
            print("❌ ERRO:", r.status_code)
            try:
                print(json.dumps(r.json(), indent=2, ensure_ascii=False))
            except Exception:
                print(r.text)
            raise SystemExit("Falhou")

        data = r.json()
        print("OK! order_id:", data.get("id"))
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data

if __name__ == "__main__":
    # O hash do cartão (encrypted_hash)
    hash_cartao = "hvBMC/BKNwF8B7ZKiHluRJM3h7X4PTLsMK9Rm2WgztB8np9gCAnlu4SxUqYkYqhme2PbWT9uxXXL2DLH/uzKI2w+/dUiy5Bgj93r8ThgMcu6kNeuXE4a/kXPwAdo1j4wU8y5AIAJTb5PD48Q88qCCz+FB9u6fRANGTg3WHRREBanc38X0KyZOcUj28t9iBiUyvn7e4dJtmfIwGc46y45X8/HoQepC00yiCtbBVRk7Sd+VcPMYa7ZcQsifBq2HrOwWUaEgZSemqwKXnUUmO128+AuQZXk4D5D4VPsbaevzF4NWjPJhmRewUiEdfzws6meK/Hn2RVyISlgOj6IOPjdLg=="
    
    # --- A CORREÇÃO ESTÁ AQUI ---
    asyncio.run(criar_e_pagar(hash_cartao))