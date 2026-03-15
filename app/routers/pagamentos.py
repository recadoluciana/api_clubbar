# app/routers/pagamentos.py
from __future__ import annotations

import os
import uuid
from typing import Any, Dict
import traceback
from fastapi.responses import HTMLResponse
from fastapi import Query

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pagamentos import PagarNovoIn, PagarNovoOut

from app.models.venda import Venda 

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
            resp = await client.post(
                f"{PAGBANK_BASE}/orders",
                json=order_body,
                headers=headers
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
    if not PAGBANK_TOKEN:
        raise HTTPException(status_code=500, detail="PAGBANK_TOKEN não configurado")

    try:
        with db.begin():
            carrinho = get_carrinho(db, payload.cliente_id, payload.organizacao_id, payload.loja_id)
            itens = carrinho.get("itens", [])

            print ("carrinho", itens)

            if not itens:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Carrinho vazio")

            minha_chave = payload.idempotency_key or str(uuid.uuid4())

            venda = await criar_ou_obter_venda_idempotente(
                db,
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

        print("[PAGAR_NOVO] venda_id =", venda_id)
        print("[PAGAR_NOVO] idempotency_key =", minha_chave)
        print("[PAGAR_NOVO] encrypted_len =", len(payload.encrypted_card or ""))

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        print("[PAGAR_NOVO][ERRO_PREPARO]", repr(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao preparar pagamento ({type(e).__name__}): {e}"
        )

    try:
        data = await _pagbank_create_order(order_body, minha_chave)
    except HTTPException as e:
        print("[PAGAR_NOVO][ERRO_PAGBANK] HTTPException")
        print("[PAGAR_NOVO][ERRO_PAGBANK] detail =", e.detail)
        raise
    except Exception as e:
        import traceback
        print("[PAGAR_NOVO][ERRO_CALL_PAGBANK]", repr(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=502,
            detail=f"Falha ao chamar PagBank ({type(e).__name__}): {e}"
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
            detail=f"Pagamento via pagbank ok, mas falhou ao salvar venda como paga. ({type(e).__name__}): {e}"
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

    nmcliente  = "Angela Binatto"
    nmloja     = "Remelexo Brasil"
    cpfcliente = "29419781860" 
    telcliente = "35999881045" 
    nrcartao   = "4539620659922097"
    mescartao  = '12'
    anocartao  = '2030'

    html = f"""
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
        const number = document.getElementById("number").value.replace(/\\D/g, "");
        const expMonth = document.getElementById("exp_month").value.replace(/\\D/g, "");
        const expYear = document.getElementById("exp_year").value.replace(/\\D/g, "");
        const cvv = document.getElementById("cvv").value.replace(/\\D/g, "");

        if (!holder || !number || !expMonth || !expYear || !cvv) {{
          setMsg("Preencha todos os campos.");
          btn.disabled = false;
          pagando = false;
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
          btn.disabled = false;
          pagando = false;
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

        if (!resp.ok) {{
          let msg = "Erro ao pagar.";

          try {{
            if (data && data.detail) {{
              msg = (typeof data.detail === "string")
                ? data.detail
                : JSON.stringify(data.detail);
            }} else {{
              msg = JSON.stringify(data);
            }}
          }} catch (e) {{
            console.log("Erro ao montar mensagem:", e);
          }}

          setMsg(msg);
          console.log("ERRO PAGAR:", data);

          btn.disabled = false;
          pagando = false;
          return;
        }}

        const status = (data.status || "").toUpperCase();

        if (status === "PAID" || status === "AUTHORIZED") {{
          setMsg("Pagamento aprovado! Você já pode voltar ao app.");
          return;
        }} else {{
          setMsg("Pagamento retornou: " + status);
          btn.disabled = false;
          pagando = false;
          return;
        }}

      }} catch (e) {{
        console.error("Falha no pagamento:", e);
        setMsg("Falha ao processar pagamento: " + (e?.message || e));
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
async def pagamento_pendente(cliente_id: int, organizacao_id: int, loja_id: int, db: Session = Depends(get_db)):
    venda = (
        db.query(Venda)
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.organizacao_id == organizacao_id,
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