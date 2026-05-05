# app/routers/pagamentos.py
from __future__ import annotations

import os
import uuid
from typing import Any, Dict
import traceback

import httpx
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pagamentos import PagarNovoIn, PagarNovoOut

from app.models.venda import Venda
from app.models.produto import Produto

from app.services.carrinho_service import get_carrinho
from app.services.venda_service import criar_ou_obter_venda_idempotente
from app.services.pagamento_status_service import (
    set_venda_como_paga,
    set_venda_como_cancelada,
)
from app.services.cliente_service import get_cliente

# ajuste este import se calcular_preco_final estiver em outro lugar
from app.routers.produtos import calcular_preco_final

from app.models.pagvenda import PagVenda

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


def _recalcular_itens_carrinho(
    db: Session, itens: list[Dict[str, Any]]
) -> tuple[list[Dict[str, Any]], float]:
    itens_recalculados = []
    total = 0.0

    for it in itens:
        produto_id = int(it.get("produto_id") or 0)
        qt = int(it.get("qt") or 1)

        produto = (
            db.query(Produto)
            .filter(Produto.produto_id == produto_id)
            .first()
        )

        if not produto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produto {produto_id} não encontrado",
            )

        if (produto.sitproduto or "").upper() != "ATIVO":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produto '{produto.nmproduto}' não está disponível",
            )

        vrprecofinal, descontoativo = calcular_preco_final(produto)
        vrunitario = float(vrprecofinal)
        subtotal = vrunitario * qt
        total += subtotal

        itens_recalculados.append(
            {
                "produto_id": produto.produto_id,
                "nmproduto": produto.nmproduto,
                "qt": qt,
                "vrunitario": vrunitario,
                "subtotal": subtotal,
                "tipodesconto": produto.tipodesconto or "NENHUM",
                "vrdesconto": float(produto.vrdesconto or 0),
                "descontoativo": descontoativo,
            }
        )

    return itens_recalculados, total

#-------------------------------------------------------------------------------
#   constroi o body para pagamento em cartão
#-------------------------------------------------------------------------------
def _build_order_body(
    venda_id: int,
    total: float,
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
                "unit_amount": _to_cents(it.get("vrunitario", 0)),
            }
        )

    cpf = _clean_digits(cliente.get("cpf"))
    ddd = _clean_digits(cliente.get("ddd"))
    telefone = _clean_digits(cliente.get("telefone"))

    phones = []
    if ddd and telefone:
        phones.append(
            {
                "country": "55",
                "area": ddd,
                "number": telefone,
                "type": "MOBILE",
            }
        )

    customer = {
        "name": cliente.get("nome", "Cliente"),
        "email": cliente.get("email", "cliente@exemplo.com"),
    }

    if cpf:
        customer["tax_id"] = cpf

    if phones:
        customer["phones"] = phones

    holder = {
        "name": cliente.get("nome", "Cliente"),
    }

    if cpf:
        holder["tax_id"] = cpf

    return {
        "reference_id": str(venda_id),
        "customer": customer,
        "items": pagbank_items,
        "charges": [
            {
                "reference_id": f"charge-{venda_id}",
                "description": f"Venda {venda_id} - ClubBar",
                "amount": {
                    "value": _to_cents(total),
                    "currency": "BRL",
                },
                "payment_method": {
                    "type": "CREDIT_CARD",
                    "installments": 1,
                    "capture": True,
                    "card": {
                        "encrypted": encrypted_card,
                        "security_code": security_code,
                        "holder": holder,
                    },
                },
            }
        ],
    }


#-------------------------------------------------------------------------------
#   constroi o body para pagamento em pix
#-------------------------------------------------------------------------------
def _build_pix_order_body(
    venda_id: int,
    total: float,
    cliente: Dict[str, Any],
) -> Dict[str, Any]:
    cpf = _clean_digits(cliente.get("cpf"))

    return {
        "reference_id": str(venda_id),
        "customer": {
            "name": cliente.get("nome", "Cliente"),
            "email": cliente.get("email", "cliente@teste.com"),
            "tax_id": cpf or "12345678909",
        },
        "items": [
            {
                "reference_id": str(venda_id),
                "name": "Pedido Clubbar",
                "quantity": 1,
                "unit_amount": _to_cents(total),
            }
        ],
        "qr_codes": [
            {
                "amount": {
                    "value": _to_cents(total),
                }
            }
        ],
    }


async def _pagbank_create_order(
    order_body: Dict[str, Any], idempotency_key: str
) -> Dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {PAGBANK_TOKEN}",
        "Content-Type": "application/json",
        "x-idempotency-key": idempotency_key,
    }

    try:
        async with httpx.AsyncClient(timeout=PAGBANK_TIMEOUT) as client:
            resp = await client.post(
                f"{PAGBANK_BASE}/orders",
                json=order_body,
                headers=headers,
            )

        print("[PAGBANK] status =", resp.status_code)

        if resp.status_code >= 400:
            try:
                body = resp.json()
            except Exception:
                body = {"text": resp.text}

            print("[PAGBANK] body erro =", body)

            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "pagbank_status": resp.status_code,
                    "body": body,
                },
            )

        data = resp.json()
        print("[PAGBANK] body ok =", data)
        return data

    except httpx.HTTPError as e:
        print("[PAGBANK][HTTP_ERROR]", repr(e))
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


# --------------------------------------------------------------------------
#  Rota para chamar pagbank para cartão e ou pix e gravar venda 
# --------------------------------------------------------------------------
@router.post("/pagar-novo")
async def pagar_novo(payload: PagarNovoIn, db: Session = Depends(get_db)):
    print("pagar-novo", payload.organizacao_id)

    if not PAGBANK_TOKEN:
        raise HTTPException(status_code=500, detail="PAGBANK_TOKEN não configurado")

    try:
        with db.begin():
            carrinho = get_carrinho(db, payload.cliente_id, payload.loja_id)

            if not carrinho:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Carrinho não encontrado",
                )

            itens = carrinho.get("itens") or []

            if not isinstance(itens, list):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Formato inválido dos itens do carrinho",
                )

            print("[PAGAR_NOVO] itens carrinho =", itens)

            if not itens:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Carrinho vazio",
                )

            # 🔥 RECALCULA TUDO COM PREÇO ATUAL
            itens_recalculados, total_recalculado = _recalcular_itens_carrinho(db, itens)

            print("[PAGAR_NOVO] itens recalculados =", itens_recalculados)
            print("[PAGAR_NOVO] total recalculado =", total_recalculado)

            minha_chave = payload.idempotency_key or str(uuid.uuid4())

            # mantém sua lógica atual de venda idempotente
            venda = await criar_ou_obter_venda_idempotente(
                db,
                cliente_id=payload.cliente_id,
                organizacao_id=payload.organizacao_id,
                loja_id=payload.loja_id,
                carrinho={
                    **carrinho,
                    "total": total_recalculado,
                    "itens": itens_recalculados,
                },
                chave=minha_chave,
                metodo_pagamento=payload.dsmetodopag,
            )

            if not venda:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Não foi possível criar/obter a venda",
                )

            venda_id = int(venda["venda_id"])

            cliente = get_cliente(db, payload.cliente_id)
            if not cliente:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Cliente não encontrado",
                )

            if (payload.dsmetodopag or "").upper() == "PIX":
                order_body = _build_pix_order_body(
                    venda_id=venda_id,
                    total=total_recalculado,
                    cliente=cliente,
                )
            else:
                order_body = _build_order_body(
                    venda_id=venda_id,
                    total=total_recalculado,
                    itens=itens_recalculados,
                    cliente=cliente,
                    encrypted_card=payload.encrypted_card,
                    security_code=payload.security_code,
                )

        print("[PAGAR_NOVO] venda_id =", venda_id)
        print("[PAGAR_NOVO] idempotency_key =", minha_chave)
        print("[PAGAR_NOVO] encrypted_len =", len(payload.encrypted_card or ""))

    except HTTPException:
        raise
    except Exception as e:
        print("[PAGAR_NOVO][ERRO_PREPARO]", repr(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao preparar pagamento ({type(e).__name__}): {e}",
        )

    # =========================
    # FASE 2 (sem DB/lock): chama PagBank
    # =========================
    try:
        data = await _pagbank_create_order(order_body, minha_chave)
    except HTTPException as e:
        print("[PAGAR_NOVO][ERRO_PAGBANK] HTTPException")
        print("[PAGAR_NOVO][ERRO_PAGBANK] detail =", e.detail)
        raise
    except Exception as e:
        print("[PAGAR_NOVO][ERRO_CALL_PAGBANK]", repr(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao chamar PagBank ({type(e).__name__}): {e}",
        )

    # =========================
    # FASE 3 (DB curto): grava retorno / marca como paga
    # =========================
    metodo = (payload.dsmetodopag or "CREDITO").upper()
    paid, charge_status = _is_paid(data)

    try:
        with db.begin():
            pagvenda_id = int(venda["pagvenda_id"])

            pag = (
                db.query(PagVenda)
                .filter(PagVenda.pagvenda_id == pagvenda_id)
                .with_for_update()
                .first()
            )

            if not pag:
                raise HTTPException(status_code=404, detail="PagVenda não encontrada")

            if metodo == "PIX":
                qr_codes = data.get("qr_codes") or []
                qr_code = qr_codes[0] if qr_codes else {}

                links = data.get("links") or []
                pay_url = ""

                for link in links:
                    if link.get("rel") == "PAY":
                        pay_url = link.get("href", "")
                        break

                pag.dsmetodopag = "PIX"
                pag.idtransacaopagvenda = data.get("id")  # ORDE_xxx
                pag.checkout_id = qr_code.get("id", "")   # QRCO_xxx
                pag.pay_url = pay_url
                pag.reference_id = str(venda_id)
                pag.provedor = "PAGBANK"

            else:
                charge = (data.get("charges") or [{}])[0]

                pag.dsmetodopag = "DEBITO" if metodo == "DEBITO" else "CREDITO"
                pag.idtransacaopagvenda = charge.get("id")  # CHAR_xxx
                pag.checkout_id = data.get("id")            # ORDE_xxx
                pag.pay_url = None
                pag.reference_id = str(venda_id)
                pag.provedor = "PAGBANK"

            if paid:
                set_venda_como_paga(
                    db,
                    venda_id=venda_id,
                    gateway="PAGBANK",
                    payload=data,
                )
            elif charge_status in {"CANCELED", "CANCELLED"}:
                set_venda_como_cancelada(
                    db,
                    venda_id=venda_id,
                    gateway="PAGBANK",
                    payload=data,
                )

    except HTTPException:
        raise
    except Exception as e:
        print("[PAGAR_NOVO][ERRO_FASE_3]", repr(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Pagamento via PagBank ok, mas falhou ao atualizar banco. ({type(e).__name__}): {e}",
        )

    if metodo == "PIX":
        qr_codes = data.get("qr_codes") or []
        qr_code = qr_codes[0] if qr_codes else {}

        return {
            "venda_id": venda_id,
            "pagbank_order_id": data.get("id"),
            "status": "PENDENTE",
            "pix_copia_cola": qr_code.get("text", ""),
            "pagbank_qrcode_id": qr_code.get("id", ""),
            "pay_url": pay_url,
        }

    return PagarNovoOut(
        venda_id=venda_id,
        pagbank_order_id=data.get("id"),
        status=charge_status or "UNKNOWN",
    )


@router.get("/pendente")
async def pagamento_pendente(
    cliente_id: int,
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
):
    venda = (
        db.query(Venda)
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.loja_id == loja_id,
            Venda.sitvenda.in_(["PENDENTE", "PAGA"]),
        )
        .order_by(Venda.venda_id.desc())
        .first()
    )

    if not venda:
        return {"ok": True, "found": False}

    return {
        "ok": True,
        "found": True,
        "venda_id": venda.venda_id,
        "sitvenda": venda.sitvenda,
    }


@router.post("/webhook/pagbank")
async def webhook_pagbank(request: Request, db: Session = Depends(get_db)):
    try:
        data = await request.json()

        print("[WEBHOOK_PAGBANK] payload =", data)

        reference_id = data.get("reference_id")
        if not reference_id:
            raise HTTPException(status_code=400, detail="reference_id não recebido")

        try:
            venda_id = int(reference_id)
        except Exception:
            raise HTTPException(status_code=400, detail="reference_id inválido")

        charge = {}
        charges = data.get("charges") or []

        if charges and isinstance(charges, list):
            charge = charges[0] or {}

        charge_status = (charge.get("status") or data.get("status") or "").upper()

        print("[WEBHOOK_PAGBANK] venda_id =", venda_id)
        print("[WEBHOOK_PAGBANK] status =", charge_status)

        if charge_status in {"PAID", "AUTHORIZED"}:
            set_venda_como_paga(
                db,
                venda_id=venda_id,
                gateway="PAGBANK",
                payload=data,
            )

        elif charge_status in {"CANCELED", "CANCELLED", "DECLINED"}:
            set_venda_como_cancelada(
                db,
                venda_id=venda_id,
                gateway="PAGBANK",
                payload=data,
            )

        return {
            "ok": True,
            "venda_id": venda_id,
            "status": charge_status,
        }

    except HTTPException:
        raise

    except Exception as e:
        print("[WEBHOOK_PAGBANK][ERRO]", repr(e))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pix/sandbox-pay/{venda_id}")
async def pix_sandbox_pay(venda_id: int, db: Session = Depends(get_db)):
    try:
        pag = (
            db.query(PagVenda)
            .filter(
                PagVenda.venda_id == venda_id,
                PagVenda.dsmetodopag == "PIX",
                PagVenda.sitpagvenda == "PENDENTE",
            )
            .order_by(PagVenda.pagvenda_id.desc())
            .first()
        )

        if not pag:
            raise HTTPException(status_code=404, detail="PIX pendente não encontrado")

        if not pag.pay_url:
            raise HTTPException(status_code=400, detail="pay_url não gravado na PagVenda")

        headers = {
            "Authorization": f"Bearer {PAGBANK_TOKEN}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=PAGBANK_TIMEOUT) as client:
            pay_resp = await client.post(
                pag.pay_url,
                headers=headers,
                json={},
            )

        if pay_resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=pay_resp.text)

        data = pay_resp.json()

        resultado = set_venda_como_paga(
            db,
            venda_id=venda_id,
            gateway="PAGBANK",
            payload=data,
        )

        db.commit()

        return {
            "ok": True,
            "venda_id": venda_id,
            "pagvenda_id": int(pag.pagvenda_id),
            "status": "PAGO",
            "resultado": resultado,
            "pagbank": data,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        print("[PIX SANDBOX PAY][ERRO]", repr(e))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))