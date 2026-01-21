# app/routers/webhooks_pagbank.py
from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime

from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.venda import Venda
from app.models.pagvenda import PagVenda

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

PAGBANK_TOKEN = os.getenv("PAGBANK_TOKEN", "").strip()


def validar_assinatura_pagbank(raw_body: bytes, header_signature: str) -> bool:
    """
    A documentação do PagBank descreve validação por SHA-256 no header de assinatura. :contentReference[oaicite:13]{index=13}
    IMPORTANTE: use o body bruto (bytes) exatamente como chegou.
    """
    if not PAGBANK_TOKEN:
        return False
    base = (PAGBANK_TOKEN + "-").encode("utf-8") + raw_body
    digest = hashlib.sha256(base).hexdigest()
    return hmac.compare_digest(digest, header_signature)


def extrair_reference_id(payload: dict) -> str | None:
    # Varia conforme evento. Tentamos os lugares mais comuns.
    # Se você me colar um exemplo real do payload, eu deixo 100% certeiro.
    return (
        payload.get("reference_id")
        or payload.get("data", {}).get("reference_id")
        or payload.get("checkout", {}).get("reference_id")
    )


def status_pago(payload: dict) -> bool | None:
    """
    Retorna:
    - True: pago/confirmado
    - False: cancelado/negado
    - None: ainda pendente / evento não conclusivo
    """
    # Como o formato do payload pode variar por tipo de evento,
    # fazemos uma checagem conservadora por campos de status.
    s = (
        payload.get("status")
        or payload.get("data", {}).get("status")
        or payload.get("checkout", {}).get("status")
    )
    if not s:
        return None

    s = str(s).upper()
    if s in ("PAID", "AUTHORIZED", "CONFIRMED", "COMPLETED", "SUCCEEDED", "PAGO"):
        return True
    if s in ("CANCELED", "CANCELLED", "DENIED", "DECLINED", "FAILED", "CANCELADO"):
        return False
    return None


@router.post("/pagbank")
async def webhook_pagbank(request: Request, db: Session = Depends(get_db)):
    raw = await request.body()
    signature = request.headers.get("x-authenticity-token")

    # Se vier assinatura, valida. (Doc: autenticar webhook por assinatura SHA-256) :contentReference[oaicite:14]{index=14}
    if signature:
        if not validar_assinatura_pagbank(raw, signature):
            raise HTTPException(status_code=401, detail="Assinatura inválida")
    else:
        # Em sandbox pode acontecer de não vir (há relatos). :contentReference[oaicite:15]{index=15}
        # Você pode optar por exigir assinatura apenas em produção.
        pass

    payload = await request.json()

    ref = extrair_reference_id(payload)
    if not ref:
        raise HTTPException(400, "reference_id não encontrado no payload")

    pag = db.query(PagVenda).filter(PagVenda.reference_id == ref).order_by(PagVenda.pagvenda_id.desc()).first()
    if not pag:
        raise HTTPException(404, "Pagamento (pagvenda) não encontrado para esse reference_id")

    venda = db.query(Venda).filter(Venda.venda_id == pag.venda_id).first()
    if not venda:
        raise HTTPException(404, "Venda não encontrada")

    decisao = status_pago(payload)

    try:
        if decisao is True:
            pag.sitpagvenda = "CONFIRMADO"
            pag.dtconftranspagvenda = datetime.utcnow()
            # se houver id de transação no payload, você pode salvar aqui:
            pag.idtransacaopagvenda = (
                payload.get("id")
                or payload.get("transaction_id")
                or payload.get("data", {}).get("id")
            )
            venda.sitvenda = "PAGA"

            # Opcional: limpar carrinho do cliente após pago (você pode fazer em outra rotina)
            # (eu prefiro limpar ITCARRINHO, não apagar o carrinho)
        elif decisao is False:
            pag.sitpagvenda = "CANCELADO"
            venda.sitvenda = "CANCELADA"
        else:
            # evento sem decisão final: mantém PENDENTE/ABERTA
            pass

        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Erro ao processar webhook: {e}")
