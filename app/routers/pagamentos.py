# app/routers/pagamentos.py
from __future__ import annotations

import os
import uuid
from typing import Any, Dict
import traceback
from fastapi import Body

from datetime import datetime, timedelta, timezone

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


# ---------- Rota ----------
@router.post("/pagar-novo", response_model=PagarNovoOut)
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
    # FASE 3 (DB curto): grava status / marca como paga
    # =========================
    paid, charge_status = _is_paid(data)

    try:
        with db.begin():
            if paid:
                set_venda_como_paga(db, venda_id=venda_id, gateway="PAGBANK", payload=data)
            elif charge_status in {"CANCELED", "CANCELLED"}:
                set_venda_como_cancelada(
                    db, venda_id=venda_id, gateway="PAGBANK", payload=data
                )
    except HTTPException:
        raise
    except Exception as e:
        print("[PAGAR_NOVO][ERRO] prepare:", repr(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Pagamento via pagbank ok, mas falhou ao salvar venda como paga. ({type(e).__name__}): {e}",
        )

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


@router.post("/pagar-pix")
async def pagar_pix(
    payload: dict = Body(...),
    db: Session = Depends(get_db),
):
    try:
        cliente_id     = int(payload.get("cliente_id") or 0)
        organizacao_id = int(payload.get("organizacao_id") or 0)
        loja_id        = int(payload.get("loja_id") or 0)

        if cliente_id <= 0 or organizacao_id <= 0 or loja_id <= 0:
            raise HTTPException(
                status_code=400,
                detail="cliente_id, organizacao_id e loja_id são obrigatórios",
            )

        carrinho = get_carrinho(db, cliente_id, loja_id)

        if not carrinho or not carrinho.get("itens"):
            raise HTTPException(status_code=400, detail="Carrinho vazio")

        itens = carrinho["itens"]
        itens_recalculados, total = _recalcular_itens_carrinho(db, itens)

        venda = await criar_ou_obter_venda_idempotente(
            db,
            cliente_id=cliente_id,
            organizacao_id=organizacao_id,
            loja_id=loja_id,
            carrinho={
                **carrinho,
                "total": total,
                "itens": itens_recalculados,
            },
            chave=str(uuid.uuid4()),
            metodo_pagamento="PIX",
        )

        venda_id = int(venda["venda_id"])

        cliente = get_cliente(db, cliente_id)
        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")

        data = await _pagbank_create_pix(
            venda_id=venda_id,
            total=total,
            cliente=cliente,
            idempotency_key=str(uuid.uuid4()),
        )

        print("[PAGBANK PIX] resposta =", data)

        qr_codes = data.get("qr_codes") or []
        qr_code = qr_codes[0] if qr_codes else {}

        links = data.get("links") or []
        pay_url = ""

        for link in links:
            if link.get("rel") == "PAY":
                pay_url = link.get("href", "")
                break

        venda_id = int(venda["venda_id"])
        pagvenda_id = int(venda["pagvenda_id"])

        pagvenda = (
            db.query(PagVenda)
            .filter(PagVenda.pagvenda_id == pagvenda_id)
            .first()
        )

        if pagvenda:
            pagvenda.dsmetodopag = "PIX"
            pagvenda.vrpagvenda = total
            pagvenda.sitpagvenda = "PENDENTE"
            pagvenda.idtransacaopagvenda = data.get("id")
            pagvenda.reference_id = str(venda_id)
            pagvenda.checkout_id = qr_code.get("id", "")
            pagvenda.pay_url = pay_url
            pagvenda.provedor = "PAGBANK"

            db.commit()
            db.refresh(pagvenda)
                
        return {
            "status": "PENDENTE",
            "venda_id": venda_id,
            "pagvenda_id": pagvenda_id,
            "pix_copia_cola": qr_code.get("text", ""),
            "qr_code_base64": "",
            "pagbank_order_id": data.get("id"),
            "pagbank_qrcode_id": qr_code.get("id", ""),
            "pay_url": pay_url,
        }

    except HTTPException:
        raise
    except Exception as e:
        print("ERRO PIX REAL:", e)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

async def _pagbank_create_pix(
    venda_id: int,
    total: float,
    cliente: Dict[str, Any],
    idempotency_key: str,
):
    headers = {
        "Authorization": f"Bearer {PAGBANK_TOKEN}",
        "Content-Type": "application/json",
        "x-idempotency-key": idempotency_key,
    }

    cpf = _clean_digits(cliente.get("cpf"))

    expiration_date = (
        datetime.now(timezone.utc) + timedelta(hours=1)
    ).isoformat(timespec="seconds")
    
    body = {
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

    async with httpx.AsyncClient(timeout=PAGBANK_TIMEOUT) as client:
        resp = await client.post(
            f"{PAGBANK_BASE}/orders",
            json=body,
            headers=headers,
        )

    if resp.status_code >= 400:
        try:
            erro = resp.json()
        except:
            erro = resp.text

        print("ERRO PAGBANK PIX:", erro)

        raise HTTPException(
            status_code=502,
            detail=erro,
        )

    return resp.json()


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
    venda = db.query(Venda).filter(Venda.venda_id == venda_id).first()

    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")

    order_id = venda.idpagbankorder  # ajuste para o nome real do campo

    headers = {
        "Authorization": f"Bearer {PAGBANK_TOKEN}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=PAGBANK_TIMEOUT) as client:
        pay_resp = await client.post(
            f"{PAGBANK_BASE}/orders/{order_id}/pay",
            headers=headers,
            json={},
        )

    if pay_resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=pay_resp.text)

    data = pay_resp.json()

    set_venda_como_paga(
        db,
        venda_id=venda_id,
        gateway="PAGBANK_PIX_SANDBOX",
        payload=data,
    )

    return {
        "ok": True,
        "venda_id": venda_id,
        "status": "PAID",
        "pagbank": data,
    }