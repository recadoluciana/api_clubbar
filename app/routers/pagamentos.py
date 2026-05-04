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


@router.get("/cartao-web", response_class=HTMLResponse)
async def cartao_web(
    cliente_id: int = Query(...),
    organizacao_id: int = Query(...),
    loja_id: int = Query(...),
):
    public_key = os.getenv("PAGBANK_PUBLIC_KEY", "")

    nmcliente = "Angela Binatto"
    nmloja = "Remelexo Brasil"
    cpfcliente = "29419781860"
    telcliente = "35999881045"
    nrcartao = "4539620659922097"
    mescartao = "12"
    anocartao = "2030"

    html = rf"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Pagamento ClubBar</title>
  <script src="https://assets.pagseguro.com.br/checkout-sdk-js/rc/dist/browser/pagseguro.min.js"></script>
  <style>
    body {{
      font-family: Arial, sans-serif;
      background: #f6f6f6;
      margin: 0;
      padding: 24px;
    }}
    .box {{
      max-width: 420px;
      margin: 0 auto;
      background: #fff;
      border-radius: 16px;
      padding: 20px;
      box-shadow: 0 4px 20px rgba(0,0,0,.08);
    }}
    h2 {{
      margin-top: 0;
      text-align: center;
    }}
    input {{
      width: 100%;
      box-sizing: border-box;
      padding: 12px;
      margin-bottom: 12px;
      border: 1px solid #ccc;
      border-radius: 10px;
      font-size: 16px;
    }}
    button {{
      width: 100%;
      padding: 14px;
      border: none;
      border-radius: 10px;
      background: #111;
      color: #fff;
      font-size: 16px;
      cursor: pointer;
    }}
    button:disabled {{
      opacity: .65;
      cursor: not-allowed;
    }}
    .msg {{
      margin-top: 12px;
      text-align: center;
      font-size: 14px;
      word-break: break-word;
    }}
  </style>
</head>
<body>
  <div class="box">
    <h2>Pagar com Cartão</h2>

    <input id="nmloja"      value="{nmloja}"     placeholder="Nome do Estabelecimento" readonly/>
    <input id="nmcliente"   value="{nmcliente}"  placeholder="Nome do Cliente" readonly />
    <input id="cpfcliente"  value="{cpfcliente}" placeholder="CPF do Cliente" />
    <input id="telcliente"  value="{telcliente}" placeholder="Telefone do Cliente" />
    <input id="holder"      value="{nmcliente}"  placeholder="Nome no cartão" />
    <input id="number"      value="{nrcartao}"   placeholder="Número do cartão" inputmode="numeric" />
    <input id="exp_month"   value="{mescartao}"  placeholder="MM" inputmode="numeric" />
    <input id="exp_year"    value="{anocartao}"  placeholder="AAAA" inputmode="numeric" />
    <input id="cvv" placeholder="CVV" inputmode="numeric" />

    <button id="btnPagar" onclick="pagar()">Pagar agora</button>

    <div class="msg" id="msg"></div>
  </div>

    <script>
      const PUBLIC_KEY = "{public_key}";
      const cliente_id = {cliente_id};
      const organizacao_id = {organizacao_id};
      const loja_id = {loja_id};

      let pagando = false;

      function setMsg(text) {{
        document.getElementById("msg").innerText = text || "";
      }}

      async function pagar() {{
        if (pagando) {{
          return;
        }}

        pagando = true;

        const btn = document.getElementById("btnPagar");
        btn.disabled = true;
        setMsg("Gerando cartão criptografado...");

        try {{
          const holder = document.getElementById("holder").value.trim();
          const number = document.getElementById("number").value.replace(/\D/g, "");
          const expMonth = document.getElementById("exp_month").value.replace(/\D/g, "");
          const expYear = document.getElementById("exp_year").value.replace(/\D/g, "");
          const cvv = document.getElementById("cvv").value.replace(/\D/g, "");

          if (!holder || !number || !expMonth || !expYear || !cvv) {{
            setMsg("Preencha todos os campos.");
            return;
          }}

          const card = PagSeguro.encryptCard({{
            publicKey: PUBLIC_KEY,
            holder: holder,
            number: number,
            expMonth: expMonth,
            expYear: expYear,
            securityCode: cvv
          }});

          if (!card || card.hasErrors || !card.encryptedCard) {{
            console.log("ERRO ENCRYPT:", card);
            setMsg("Dados do cartão inválidos.");
            return;
          }}

          setMsg("Processando pagamento...");
          console.log("POST /pagamentos/pagar-novo");
          console.log("encrypted len:", (card.encryptedCard || "").length);

          const resp = await fetch("/pagamentos/pagar-novo", {{
            method: "POST",
            headers: {{
              "Content-Type": "application/json"
            }},
            body: JSON.stringify({{
              cliente_id: cliente_id,
              organizacao_id: organizacao_id,
              loja_id: loja_id,
              encrypted_card: card.encryptedCard,
              security_code: cvv,
              idempotency_key: null
            }})
          }});

          const data = await resp.json();
          console.log("HTTP status:", resp.status);
          console.log("Resposta do backend:", data);

          if (!resp.ok) {{
            const msg =
              data?.detail?.mensagem ||
              data?.detail?.message ||
              data?.mensagem ||
              data?.message ||
              "Erro no pagamento";
            throw new Error(msg);
          }}

          const statusPagamento =
            data?.status ||
            data?.sitpagvenda ||
            data?.situacao ||
            (data?.ok ? "PAID" : null);

          if (statusPagamento === "PAID" || statusPagamento === "PAGO") {{
            setMsg("Pagamento aprovado com sucesso");
          }} else {{
            setMsg(statusPagamento || "Pagamento concluído. Pode voltar para o seu app");
          }}

        }} catch (err) {{
          console.error("Erro no pagamento:", err);
          setMsg(err.message || "Erro ao processar pagamento");
        }} finally {{
          btn.disabled = false;
          pagando = false;
        }}
      }}
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html)


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
        cliente_id = int(payload.get("cliente_id") or 0)
        organizacao_id = int(payload.get("organizacao_id") or 0)
        loja_id = int(payload.get("loja_id") or 0)

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

        charge = (data.get("charges") or [{}])[0]
        payment_method = charge.get("payment_method") or {}
        qr_codes = payment_method.get("qr_codes") or []

        qr_code = qr_codes[0] if qr_codes else {}

        return {
            "status": charge.get("status", "PENDENTE"),
            "venda_id": venda_id,
            "pix_copia_cola": qr_code.get("text", ""),
            "qr_code_base64": "",
            "pagbank_order_id": data.get("id"),
            "pagbank_charge_id": charge.get("id"),
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

        "notification_urls": [  # ✅ CORRETO
            "https://bitbeer-production.up.railway.app/pagamentos/webhook/pagbank"
        ],

        "customer": {
            "name": cliente.get("nome", "Cliente"),
            "email": cliente.get("email", "cliente@teste.com"),
            "tax_id": cpf or "12345678909",
        },

        "charges": [
            {
                "reference_id": f"pix-{venda_id}",
                "description": f"Venda {venda_id} - ClubBar",
                "amount": {
                    "value": _to_cents(total),
                    "currency": "BRL",
                },
                "payment_method": {
                    "type": "PIX",
                    "pix": {
                        "expiration_date": expiration_date
                    }
                },
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