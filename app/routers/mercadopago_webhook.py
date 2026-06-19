# app/routers/mercadopago_webhook.py
from __future__ import annotations
import traceback

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

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

async def criar_venda_paga_por_carrinho_mp(
    db: Session,
    *,
    carrinho_id: int,
    pagamento: dict,
):
    carrinho_db = (
        db.query(Carrinho)
        .filter(Carrinho.carrinho_id == carrinho_id)
        .filter(Carrinho.sitcarrinho == "ABERTO")
        .first()
    )

    if not carrinho_db:
        print("[MP WEBHOOK] Carrinho não encontrado ou já fechado:", carrinho_id)
        return {
            "ok": True,
            "msg": "Carrinho não encontrado ou já fechado",
            "carrinho_id": carrinho_id,
        }

    carrinho = get_carrinho(
        db,
        carrinho_db.cliente_id,
        carrinho_db.loja_id,
    )

    if not carrinho:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado")

    itens = carrinho.get("itens") or []

    if not itens:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    itens_recalculados, total_recalculado = _recalcular_itens_carrinho(
        db,
        itens,
    )

    venda = await criar_ou_obter_venda_idempotente(
        db,
        cliente_id=carrinho_db.cliente_id,
        organizacao_id=carrinho_db.organizacao_id,
        loja_id=carrinho_db.loja_id,
        carrinho={
            **carrinho,
            "total": total_recalculado,
            "itens": itens_recalculados,
        },
        chave=str(uuid.uuid4()),
        metodo_pagamento="PIX",
    )

    venda_id = int(venda["venda_id"])
    pagvenda_id = int(venda["pagvenda_id"])

    pag = (
        db.query(PagVenda)
        .filter(PagVenda.pagvenda_id == pagvenda_id)
        .with_for_update()
        .first()
    )

    if not pag:
        raise HTTPException(status_code=404, detail="PagVenda não encontrada")

    pag.dsmetodopag = "PIX"
    pag.sitpagvenda = "PAGO"
    pag.idtransacaopagvenda = str(pagamento.get("id"))
    pag.checkout_id = str(pagamento.get("id"))
    pag.reference_id = str(venda_id)
    pag.pay_url = None
    pag.provedor = "MERCADO_PAGO"

    resultado = set_venda_como_paga(
        db,
        venda_id=venda_id,
        gateway="MERCADOPAGO",
        payload=pagamento,
    )

    return {
        "ok": True,
        "venda_id": venda_id,
        "pagvenda_id": pagvenda_id,
        "resultado": resultado,
    }
    
@router.post("/consultar-pagamento/{pagamento_id}")
async def consultar_pagamento_por_id(
    pagamento_id: str,
    db: Session = Depends(get_db),
):
    pagamento = await consultar_pagamento(str(pagamento_id))

    status_mp = (pagamento.get("status") or "").lower()
    external_reference = str(pagamento.get("external_reference") or "").strip()

    resultado = None

    if external_reference.startswith("CARRINHO-"):
        carrinho_id = int(external_reference.replace("CARRINHO-", ""))

        if status_mp == "approved":
            with db.begin():
                resultado = await criar_venda_paga_por_carrinho_mp(
                    db,
                    carrinho_id=carrinho_id,
                    pagamento=pagamento,
                )

        return {
            "ok": True,
            "status": "PAGO" if status_mp == "approved" else status_mp.upper(),
            "status_mp": status_mp,
            "pagamento_id": pagamento_id,
            "carrinho_id": carrinho_id,
            "resultado": resultado,
        }

    return {
        "ok": True,
        "status": "PAGO" if status_mp == "approved" else status_mp.upper(),
        "status_mp": status_mp,
        "pagamento_id": pagamento_id,
        "external_reference": external_reference,
    }
        
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

        pagamento_id = (
            data.get("id")
            or body.get("id")
        )

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

        except Exception as e:

            print("[MP WEBHOOK] pagamento ainda indisponível")

            return {
                "ok": True,
                "mensagem": "Pagamento ainda não disponível",
            }

        print("[MP WEBHOOK] pagamento =", pagamento)

        external_reference = str(pagamento.get("external_reference") or "").strip()
        status_mp = (pagamento.get("status") or "").lower()

        if not external_reference:
            print("[MP WEBHOOK] external_reference vazio")
            return {"ok": True, "msg": "external_reference vazio"}

        if external_reference.startswith("CARRINHO-"):
            carrinho_id = int(external_reference.replace("CARRINHO-", ""))

            print("[MP WEBHOOK] carrinho_id =", carrinho_id)
            print("[MP WEBHOOK] status =", status_mp)

            resultado = None

            if status_mp == "approved":
                with db.begin():
                    resultado = await criar_venda_paga_por_carrinho_mp(
                        db,
                        carrinho_id=carrinho_id,
                        pagamento=pagamento,
                    )

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

        # approved
        if status_mp == "approved":

            with db.begin():
                set_venda_como_paga(
                    db,
                    venda_id=venda_id,
                    gateway="MERCADOPAGO",
                    payload=pagamento,
                )

        elif status_mp in {"cancelled", "rejected"}:

            with db.begin():
                set_venda_como_cancelada(
                    db,
                    venda_id=venda_id,
                    gateway="MERCADOPAGO",
                    payload=pagamento,
                    fechar_carrinho=False,
                )

        elif status_mp in {"pending", "in_process", "authorized"}:
            # Apenas registra e aguarda nova notificação
            print(f"[MP WEBHOOK] Pagamento em processamento: {status_mp}")

        elif status_mp in {"refunded", "charged_back"}:
            print(f"[MP WEBHOOK] Pagamento estornado/chargeback: {status_mp}")
            # Futuramente implementar lógica de reversão

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