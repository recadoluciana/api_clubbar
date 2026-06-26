# app/routers/mercadopago_webhook.py
from __future__ import annotations
import traceback

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from contextlib import nullcontext
from app.database import get_db

import uuid

from app.models.carrinho import Carrinho
from app.models.pagvenda import PagVenda

from app.routers.pagamentos import _recalcular_itens_carrinho
from app.services.venda_service import criar_ou_obter_venda_idempotente
from app.services.mercadopago_service import consultar_pagamento
from app.services.carrinho_service import get_carrinho

from app.services.pagamento_status_service import (
    set_venda_como_paga,
    set_venda_como_cancelada,
)

router = APIRouter(
    prefix="/mercadopago",
    tags=["Mercado Pago"],
)

    
@router.post("/consultar-pagamento/{pagamento_id}")
async def consultar_pagamento_por_id(
    pagamento_id: str,
    db: Session = Depends(get_db),
):
    pagamento = await consultar_pagamento(str(pagamento_id))

    status_mp = (pagamento.get("status") or "").lower()
    external_reference = str(pagamento.get("external_reference") or "").strip()

    return {
        "ok": True,
        "status": "PAGO" if status_mp == "approved" else status_mp.upper(),
        "status_mp": status_mp,
        "pagamento_id": pagamento_id,
        "external_reference": external_reference,
    }
     
def db_tx(db: Session):
    return nullcontext() if db.in_transaction() else db.begin()

@router.post("/webhook")
async def mercadopago_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        body = await request.json()

        print("[MP WEBHOOK] BODY =", body)

        tipo = body.get("type") or body.get("topic")
        data = body.get("data") or {}

        pagamento_id = data.get("id") or body.get("id") or body.get("resource")

        if pagamento_id:
            pagamento_id = str(pagamento_id).strip()

        if not pagamento_id:
            return {
                "ok": True,
                "mensagem": "Webhook sem payment id",
            }

        print("[MP WEBHOOK] pagamento_id =", pagamento_id)

        try:
            pagamento = await consultar_pagamento(str(pagamento_id))
        except Exception:
            print("[MP WEBHOOK] pagamento ainda indisponível")
            return {
                "ok": True,
                "mensagem": "Pagamento ainda não disponível",
            }

        print("[MP WEBHOOK] pagamento =", pagamento)

        external_reference = str(
            pagamento.get("external_reference") or ""
        ).strip()

        status_mp = (pagamento.get("status") or "").lower()

        if not external_reference:
            print("[MP WEBHOOK] external_reference vazio")
            return {"ok": True, "msg": "external_reference vazio"}

        if external_reference == "0":
            print("[MP WEBHOOK] external_reference 0 ignorado")
            return {"ok": True, "msg": "external_reference 0 ignorado"}

        if external_reference.startswith("CARRINHO-"):
            try:
                carrinho_id = int(
                    external_reference.replace("CARRINHO-", "").split("-")[0]
                )
            except Exception:
                print("[MP WEBHOOK] carrinho_id inválido:", external_reference)
                return {
                    "ok": True,
                    "msg": "carrinho_id inválido",
                    "external_reference": external_reference,
                }

            print("[MP WEBHOOK] carrinho_id =", carrinho_id)
            print("[MP WEBHOOK] status =", status_mp)

            resultado = None

            if status_mp == "approved":
                with db_tx(db):
                    resultado = await criar_venda_paga_por_carrinho_mp(
                        db,
                        carrinho_id=carrinho_id,
                        pagamento=pagamento,
                    )

            elif status_mp in {"cancelled", "rejected"}:
                print("[MP WEBHOOK] pagamento recusado/cancelado para carrinho:", carrinho_id)

            elif status_mp in {"pending", "in_process", "authorized"}:
                print("[MP WEBHOOK] pagamento em processamento:", status_mp)

            elif status_mp in {"refunded", "charged_back"}:
                print("[MP WEBHOOK] pagamento estornado/chargeback:", status_mp)

            else:
                print("[MP WEBHOOK] status não tratado:", status_mp)

            return {
                "ok": True,
                "carrinho_id": carrinho_id,
                "status": status_mp,
                "pagamento_id": pagamento_id,
                "tipo": tipo,
                "resultado": resultado,
            }

        if not external_reference.isdigit():
            print("[MP WEBHOOK] external_reference inválido:", external_reference)
            return {"ok": True, "msg": "external_reference ignorado"}

        venda_id = int(external_reference)

        print("[MP WEBHOOK] venda_id =", venda_id)
        print("[MP WEBHOOK] status =", status_mp)

        if status_mp == "approved":
            with db_tx(db):
                set_venda_como_paga(
                    db,
                    venda_id=venda_id,
                    gateway="MERCADOPAGO",
                    payload=pagamento,
                )

        elif status_mp in {"cancelled", "rejected"}:
            with db_tx(db):
                set_venda_como_cancelada(
                    db,
                    venda_id=venda_id,
                    gateway="MERCADOPAGO",
                    payload=pagamento,
                )

        elif status_mp in {"pending", "in_process", "authorized"}:
            print(f"[MP WEBHOOK] Pagamento em processamento: {status_mp}")

        elif status_mp in {"refunded", "charged_back"}:
            print(f"[MP WEBHOOK] Pagamento estornado/chargeback: {status_mp}")

        else:
            print(f"[MP WEBHOOK] Status não tratado: {status_mp}")

        return {
            "ok": True,
            "venda_id": venda_id,
            "status": status_mp,
            "pagamento_id": pagamento_id,
            "tipo": tipo,
        }

    except HTTPException:
        raise

    except Exception as e:
        print("[MP WEBHOOK][ERRO]", repr(e))
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )