from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from fastapi.responses import HTMLResponse

from app.services.venda_gateway_service import criar_venda_paga_por_carrinho_gateway
from app.models.carrinho import Carrinho

router = APIRouter(
    prefix="/asaas",
    tags=["Asaas"],
)

@router.post("/webhook")
async def asaas_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        body = await request.json()
    except Exception:
        body = {}

    print("[ASAAS WEBHOOK]")
    print(body)

    evento = body.get("event")
    payment = body.get("payment") or {}

    status = (payment.get("status") or "").upper()
    external_reference = str(payment.get("externalReference") or "").strip()

    if not external_reference.startswith("CARRINHO-"):
        return {"ok": True, "ignored": True, "msg": "externalReference ignorado"}

    carrinho_id = int(external_reference.replace("CARRINHO-", "").split("-")[0])

    if evento not in ["PAYMENT_RECEIVED", "PAYMENT_CONFIRMED"] and status not in ["RECEIVED", "CONFIRMED"]:
        return {
            "ok": True,
            "ignored": True,
            "event": evento,
            "status": status,
            "carrinho_id": carrinho_id,
        }

    resultado = await criar_venda_paga_por_carrinho_gateway(
        db,
        carrinho_id=carrinho_id,
        gateway="ASAAS",
        pagamento=payment,
        metodo_pagamento="CREDITO",
    )

    db.commit()

    return {
        "ok": True,
        "gateway": "ASAAS",
        "event": evento,
        "status": status,
        "carrinho_id": carrinho_id,
        "resultado": resultado,
    }

@router.get("/retorno", response_class=HTMLResponse)
async def asaas_retorno(
    carrinho_id: int,
    db: Session = Depends(get_db),
):
    carrinho = (
        db.query(Carrinho)
        .filter(Carrinho.carrinho_id == carrinho_id)
        .first()
    )

    pago = carrinho and (carrinho.sitcarrinho or "").upper() != "ABERTO"

    if pago:
        titulo = "Pagamento confirmado!"
        mensagem = "Sua compra foi confirmada com sucesso."
        icone = "✓"
        cor = "#19a55a"
        retorno = "sucesso"
    else:
        titulo = "Pagamento não confirmado"
        mensagem = "Sua compra ainda não foi confirmada. Se você desistiu do pagamento, nenhuma compra foi concluída."
        icone = "!"
        cor = "#d97706"
        retorno = "pendente"

    return f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>{titulo}</title>
      <style>
        body {{
          margin: 0;
          font-family: Arial, sans-serif;
          background: #f6f6f6;
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
        }}
        .card {{
          background: white;
          padding: 28px;
          border-radius: 22px;
          max-width: 420px;
          text-align: center;
          box-shadow: 0 8px 24px rgba(0,0,0,.12);
        }}
        .icone {{
          font-size: 56px;
          color: {cor};
          font-weight: bold;
        }}
        h1 {{ font-size: 24px; }}
        p {{ color: #555; line-height: 1.5; }}
        a {{
          display: inline-block;
          margin-top: 18px;
          background: #000;
          color: #fff;
          padding: 14px 22px;
          border-radius: 14px;
          text-decoration: none;
          font-weight: bold;
        }}
      </style>
    </head>
    <body>
      <div class="card">
        <div class="icone">{icone}</div>
        <h1>{titulo}</h1>
        <p>{mensagem}</p>
        <a href="https://app.clubbar.com.br/?pagamento={retorno}&gateway=asaas">
          Voltar para o Clubbar
        </a>
      </div>
    </body>
    </html>
    """