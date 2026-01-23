# app/routers/pagbank_webhook.py
from __future__ import annotations

import hashlib
import hmac
import os

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.venda import Venda
from app.models.pagvenda import PagVenda
from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho

router = APIRouter(prefix="/pagamentos", tags=["pagamentos"])

PAGBANK_TOKEN = os.getenv("PAGBANK_TOKEN", "").strip()


def validar_assinatura_pagbank(raw_body: bytes, header_signature: str) -> bool:
    """
    Se você for validar assinatura:
    - precisa saber qual header o PagBank envia (ex.: x-signature / x-hub-signature etc.)
    - e a regra exata. Aqui fica como referência.
    """
    if not PAGBANK_TOKEN or not header_signature:
        return False
    base = (PAGBANK_TOKEN + "-").encode("utf-8") + raw_body
    digest = hashlib.sha256(base).hexdigest()
    return hmac.compare_digest(digest, header_signature)


def extrair_reference_id_pagbank(data: dict) -> str | None:
    # alguns eventos vêm embrulhados em "data"
    if isinstance(data.get("data"), dict):
        ref = extrair_reference_id_pagbank(data["data"])
        if ref:
            return ref

    ref = data.get("reference_id")
    if ref:
        return ref

    charges = data.get("charges") or []
    if isinstance(charges, list):
        for ch in charges:
            ref = (ch or {}).get("reference_id")
            if ref:
                return ref

    checkout = data.get("checkout") or {}
    if isinstance(checkout, dict):
        ref = checkout.get("reference_id")
        if ref:
            return ref

    return None


def extrair_status_pagbank(data: dict) -> str:
    # 1) status no topo
    s = data.get("status")
    if s:
        return str(s).upper().strip()

    # 2) status dentro de data
    s = (data.get("data") or {}).get("status")
    if s:
        return str(s).upper().strip()

    # 3) charges[*].status
    charges = data.get("charges") or []
    if isinstance(charges, list):
        primeiro = ""
        for ch in charges:
            s = (ch or {}).get("status")
            if not s:
                continue
            st = str(s).upper().strip()
            if st == "PAID":
                return st
            if not primeiro:
                primeiro = st
        if primeiro:
            return primeiro

    return ""


@router.post("/webhook")
async def pagbank_webhook(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    print("[PAGBANK][WEBHOOK] RAW:", raw.decode("utf-8", errors="ignore"))

    # Se quiser validar assinatura, descomente e ajuste o header correto:
    # signature = request.headers.get("X-Signature", "")
    # if not validar_assinatura_pagbank(raw, signature):
    #     raise HTTPException(status_code=401, detail="Assinatura inválida")

    try:
        data = await request.json()
    except Exception:
        data = None

    print("[PAGBANK][WEBHOOK] JSON:", data)

    if not isinstance(data, dict):
        return {"ok": True, "ignored": "invalid_payload"}

    # 1) reference_id -> VENDA-XX
    reference_id = extrair_reference_id_pagbank(data)
    print("[PAGBANK][WEBHOOK] reference_id =", reference_id)

    if not reference_id or not str(reference_id).startswith("VENDA-"):
        return {"ok": True, "ignored": "no_reference_id", "reference_id": reference_id}

    try:
        venda_id = int(str(reference_id).split("-", 1)[1])
    except Exception:
        return {"ok": True, "ignored": "bad_reference_id", "reference_id": reference_id}

    # 2) status (pode vir vazio em eventos não conclusivos)
    status_charge = extrair_status_pagbank(data)
    print("[PAGBANK][WEBHOOK] status_charge =", status_charge)

    if status_charge == "":
        # evento “informativo” (ex.: order criado/qr gerado). Espera o evento com PAID.
        return {"ok": True, "ignored": "pending", "venda_id": venda_id}

    # 3) mapear status PagBank -> seu banco
    if status_charge == "PAID":
        novo_sitpag = "PAGO"
        novo_sitvenda = "PAGA"
    elif status_charge in {"CANCELED", "CANCELLED"}:
        novo_sitpag = "CANCELADO"
        novo_sitvenda = "CANCELADA"
    else:
        return {"ok": True, "ignored": "not_paid", "venda_id": venda_id, "status": status_charge}

    # 4) buscar venda e pagvenda
    venda = db.query(Venda).filter(Venda.venda_id == venda_id).first()
    pag = (
        db.query(PagVenda)
        .filter(PagVenda.venda_id == venda_id)
        .order_by(PagVenda.pagvenda_id.desc())
        .first()
    )

    if not venda or not pag:
        return {
            "ok": True,
            "ignored": "not_found",
            "venda_id": venda_id,
            "venda_encontrada": bool(venda),
            "pag_encontrada": bool(pag),
        }

    # 5) idempotência
    if (pag.sitpagvenda or "").upper() == "PAGO" and (venda.sitvenda or "").upper() in {"PAGA", "PAGO"}:
        return {"ok": True, "already_processed": True, "venda_id": venda_id}

    # 6) aplicar update + limpar carrinho (com relatório)
    try:
        pag.sitpagvenda = novo_sitpag
        venda.sitvenda = novo_sitvenda

        # 7) fechar carrinho da venda (GARANTIDO) + limpar itens
        carrinho_id = getattr(venda, "carrinho_id", None)

        if carrinho_id:
            carrinho = db.query(Carrinho).filter(Carrinho.carrinho_id == carrinho_id).first()

            if carrinho:
                # fecha o carrinho (histórico)
                carrinho.sitcarrinho = "FECHADO"

                # limpa somente os itens do carrinho (opção A)
                db.query(ItCarrinho).filter(
                    ItCarrinho.carrinho_id == carrinho.carrinho_id
                ).delete(synchronize_session=False)
        else:
            # fallback opcional (só pra log)
            print("[PAGBANK][WEBHOOK] Aviso: venda sem carrinho_id, não fechei carrinho.")

        db.commit()

        # recarrega pra confirmar o que ficou no DB
        db.refresh(venda)
        db.refresh(pag)
        db.refresh(carrinho)

        return {
            "ok": True,
            "venda_id": venda_id,
            "status": status_charge,
            "sitvenda_db": venda.sitvenda,
            "sitpagvenda_db": pag.sitpagvenda,
            "carrinho_encontrado": bool(carrinho)
        }

    except Exception as e:
        db.rollback()
        import traceback

        print("[PAGBANK][WEBHOOK] ERRO:", repr(e))
        print(traceback.format_exc())
        raise HTTPException(500, f"Erro processando webhook: {e}")