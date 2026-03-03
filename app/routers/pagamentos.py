# app/routers/pagamentos.py
from __future__ import annotations

import os
import uuid
from typing import Any, Dict
import traceback

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pagamentos import PagarNovoIn, PagarNovoOut
from app.services.carrinho_service import get_carrinho
from app.services.venda_service import criar_ou_obter_venda_idempotente
from app.services.pagamento_status_service import set_venda_como_paga, set_venda_como_cancelada
from app.services.cliente_service import get_cliente

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])

PAGBANK_BASE = os.getenv("PAGBANK_BASE", "https://sandbox.api.pagseguro.com")
PAGBANK_TOKEN = os.getenv("PAGBANK_TOKEN", "")
PAGBANK_TIMEOUT = float(os.getenv("PAGBANK_TIMEOUT", "30"))


# ---------- Helpers (internos) ----------
def _clean_digits(value: str | None) -> str:
    if not value:
        return ""
    return "".join(ch for ch in str(value) if ch.isdigit())

def _to_cents(value: Any) -> int:
    try:
        return int(round(float(value) * 100))
    except Exception:
        return 0

def _build_order_body(
    venda_id: int,
    carrinho: Dict[str, Any],
    itens: list[Dict[str, Any]],
    cliente: Dict[str, Any],
    encrypted_card: str,
    security_code: str,
) -> Dict[str, Any]:
    pagbank_items = []
    for it in itens:
        pagbank_items.append(
            {
                "reference_id": str(it.get("produto_id")),
                "name": it.get("nmproduto", "Produto"),
                "quantity": int(it.get("qt", 1)),
                "unit_amount": _to_cents(it.get("vrprecoprod", 0)),
            }
        )

    cpf = _clean_digits(cliente.get("cpf"))
    ddd = _clean_digits(cliente.get("ddd"))
    telefone = _clean_digits(cliente.get("telefone"))

    return {
        "reference_id": str(venda_id),
        "customer": {
            "name": cliente.get("nome", "Cliente"),
            "email": cliente.get("email", "cliente@exemplo.com"),
            "tax_id": cpf,
            "phones": [
                {
                    "country": "55",
                    "area": ddd,
                    "number": telefone,
                    "type": "MOBILE",
                }
            ],
        },
        "items": pagbank_items,
        "charges": [
            {
                "reference_id": f"charge-{venda_id}",
                "description": f"Venda {venda_id} - ClubBar",
                "amount": {"value": _to_cents(carrinho.get("total", 0)), "currency": "BRL"},
                "payment_method": {
                    "type": "CREDIT_CARD",
                    "installments": 1,
                    "capture": True,
                    "card": {
                        "encrypted": encrypted_card,
                        "security_code": security_code,
                        "holder": {
                            "name": cliente.get("nome", "Cliente"),
                            "tax_id": cpf,
                        },
                    },
                },
            }
        ],
    }


async def _pagbank_create_order(order_body: Dict[str, Any], idempotency_key: str) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {PAGBANK_TOKEN}",
        "Content-Type": "application/json",
        "x-idempotency-key": idempotency_key,
    }

    try:
        async with httpx.AsyncClient(timeout=PAGBANK_TIMEOUT) as client:
            resp = await client.post(f"{PAGBANK_BASE}/orders", json=order_body, headers=headers)

        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {"text": resp.text}
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"pagbank_status": resp.status_code, "body": body},
            )

        return resp.json()

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Falha ao chamar PagBank: {e}",
        )


def _is_paid(data: Dict[str, Any]) -> tuple[bool, str]:
    try:
        charge_status = data.get("charges", [{}])[0].get("status") or ""
    except Exception:
        charge_status = ""
    paid = charge_status in {"PAID", "AUTHORIZED"}
    return paid, charge_status


# ---------- Rota ----------

@router.post("/pagar-novo", response_model=PagarNovoOut)
async def pagar_novo(payload: PagarNovoIn, db: Session = Depends(get_db)):
    if not PAGBANK_TOKEN:
        raise HTTPException(status_code=500, detail="PAGBANK_TOKEN não configurado")

    # =========================
    # FASE 1 (DB curto): trava carrinho, cria venda, pega cliente, monta order_body
    # =========================
    try:
        with db.begin():
            carrinho = get_carrinho(db, payload.cliente_id, payload.organizacao_id, payload.loja_id)
            itens = carrinho.get("itens", [])
            if not itens:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Carrinho vazio")

            minha_chave = payload.idempotency_key or str(uuid.uuid4())

            # ⚠️ abaixo são suas funções (ajuste para receber db se necessário)
            venda = await criar_ou_obter_venda_idempotente(db,
                cliente_id=payload.cliente_id,
                organizacao_id=payload.organizacao_id,
                loja_id=payload.loja_id,
                carrinho=carrinho,
                chave=minha_chave,
            )
            venda_id = int(venda["venda_id"])

            cliente = get_cliente(db, payload.cliente_id)

            order_body = _build_order_body(
                venda_id=venda_id,
                carrinho=carrinho,
                itens=itens,
                cliente=cliente,
                encrypted_card=payload.encrypted_card,
                security_code=payload.security_code,
            )

        # saiu do with db.begin() -> commit, lock liberado ✅

    except HTTPException:
        # db.begin() já faz rollback se levantou erro
        raise
    except Exception as e:
        print("[PAGAR_NOVO][ERRO] prepare:", repr(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao preparar pagamento ({type(e).__name__}): {e}"
        )

    # =========================
    # FASE 2 (sem DB/lock): chama PagBank
    # =========================
    data = await _pagbank_create_order(order_body, minha_chave)

    # =========================
    # FASE 3 (DB curto): grava status / marca como paga
    # =========================
    paid, charge_status = _is_paid(data)

    try:
        with db.begin():
            if paid:
                set_venda_como_paga(db, venda_id=venda_id, gateway="PAGBANK", payload=data)
            elif charge_status in {"CANCELED", "CANCELLED"}:
                set_venda_como_cancelada(db, venda_id=venda_id, gateway="PAGBANK", payload=data)
    except HTTPException:
        raise
    except Exception as e:
        # pagamento pode ter sido aprovado mas falhou pra salvar no seu banco:
        # devolvemos erro pra você corrigir e depois você concilia via status do PagBank.
        print("[PAGAR_NOVO][ERRO] prepare:", repr(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao preparar pagamento ({type(e).__name__}): {e}"
        )

    return PagarNovoOut(
        venda_id=venda_id,
        pagbank_order_id=data.get("id"),
        status=charge_status or "UNKNOWN",
    )