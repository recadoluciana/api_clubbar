import json
import traceback

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.carrinho import Carrinho
from app.services.venda_gateway_service import criar_venda_paga_por_carrinho_gateway

from app.models.checkout_asaas import CheckoutAsaas

from app.models.cliente import Cliente
from app.services.asaas_service import buscar_customer_asaas

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

    print("=" * 80)
    print("[ASAAS WEBHOOK]")
    print(json.dumps(body, indent=2, ensure_ascii=False))
    print("=" * 80)

    try:
        evento = str(body.get("event") or "").upper()

        payment = (
            body.get("payment")
            or body.get("checkout")
            or body.get("object")
            or {}
        )

        status = str(payment.get("status") or body.get("status") or "").upper()

        checkout_id = (
            payment.get("checkoutSession")
            or body.get("checkoutId")
            or body.get("checkoutSession")
        )

        payment_id = payment.get("id") or body.get("paymentId")

        registro_checkout = None

        if checkout_id:
            registro_checkout = (
                db.query(CheckoutAsaas)
                .filter(CheckoutAsaas.checkout_id == str(checkout_id))
                .first()
            )

        external_reference = str(
            payment.get("externalReference")
            or body.get("externalReference")
            or ""
        ).strip()

        if registro_checkout:
            carrinho_id = int(registro_checkout.carrinho_id)
            external_reference = (
                registro_checkout.external_reference
                or f"CARRINHO-{carrinho_id}"
            )
        else:
            if not external_reference.startswith("CARRINHO-"):
                return {
                    "ok": True,
                    "ignored": True,
                    "msg": "Checkout/carrinho não localizado",
                    "event": evento,
                    "status": status,
                    "checkout_id": checkout_id,
                    "payment_id": payment_id,
                    "externalReference": external_reference,
                }

            carrinho_id = int(
                external_reference.replace("CARRINHO-", "").split("-")[0]
            )

        eventos_confirmados = [
            "PAYMENT_RECEIVED",
            "PAYMENT_CONFIRMED",
            "CHECKOUT_PAID",
        ]

        status_confirmados = [
            "RECEIVED",
            "CONFIRMED",
            "PAID",
        ]

        if evento not in eventos_confirmados and status not in status_confirmados:
            if registro_checkout:
                registro_checkout.status = status or evento or registro_checkout.status
                if payment_id:
                    registro_checkout.payment_id = str(payment_id)
                db.commit()

            return {
                "ok": True,
                "ignored": True,
                "event": evento,
                "status": status,
                "carrinho_id": carrinho_id,
            }

        print("[ASAAS WEBHOOK] criando venda carrinho:", carrinho_id)

        resultado = await criar_venda_paga_por_carrinho_gateway(
            db,
            carrinho_id=carrinho_id,
            gateway="ASAAS",
            pagamento=payment,
            metodo_pagamento="CREDITO",
        )

        customer_id = payment.get("customer")

        if customer_id and registro_checkout:
            customer = await buscar_customer_asaas(str(customer_id))

            cliente = (
                db.query(Cliente)
                .filter(Cliente.cliente_id == registro_checkout.cliente_id)
                .first()
            )

            if cliente:
                cliente.nrtelcliente = customer.get("mobilePhone") or customer.get("phone") or cliente.nrtelcliente
                cliente.nrcpfcliente = customer.get("cpfCnpj") or cliente.nrcpfcliente
                cliente.endcliente = customer.get("address") or cliente.endcliente
                cliente.nrendcliente = customer.get("addressNumber") or cliente.nrendcliente
                cliente.complcliente = customer.get("complement") or cliente.complcliente
                cliente.bairrocliente = customer.get("province") or cliente.bairrocliente
                cliente.cepcliente = customer.get("postalCode") or cliente.cepcliente
                cliente.cidadecliente = customer.get("city") or cliente.cidadecliente
                cliente.ufcliente = customer.get("state") or cliente.ufcliente
                
        #await sincronizar_cliente_com_asaas(
        #    db,
        #    cliente_id=registro_checkout.cliente_id,
        #)

        customer_id = payment.get("customer")

        if customer_id and registro_checkout:
            customer = await buscar_customer_asaas(str(customer_id))

            cliente = (
                db.query(Cliente)
                .filter(Cliente.cliente_id == registro_checkout.cliente_id)
                .first()
            )

            if cliente:
                cliente.nrtelcliente = customer.get("mobilePhone") or customer.get("phone") or cliente.nrtelcliente
                cliente.nrcpfcliente = customer.get("cpfCnpj") or cliente.nrcpfcliente
                cliente.endcliente = customer.get("address") or cliente.endcliente
                cliente.nrendcliente = customer.get("addressNumber") or cliente.nrendcliente
                cliente.complcliente = customer.get("complement") or cliente.complcliente
                cliente.bairrocliente = customer.get("province") or cliente.bairrocliente
                cliente.cepcliente = customer.get("postalCode") or cliente.cepcliente

        if registro_checkout:
            registro_checkout.status = "PAID"
            if payment_id:
                registro_checkout.payment_id = str(payment_id)

        db.commit()

        return {
            "ok": True,
            "gateway": "ASAAS",
            "event": evento,
            "status": status,
            "carrinho_id": carrinho_id,
            "checkout_id": checkout_id,
            "payment_id": payment_id,
            "resultado": resultado,
        }

    except Exception as e:
        db.rollback()

        print("[ASAAS WEBHOOK][ERRO]", repr(e))
        print(traceback.format_exc())

        return {
            "ok": False,
            "erro": str(e),
            "tipo": type(e).__name__,
        }


@router.get("/retorno", response_class=HTMLResponse)
async def asaas_retorno(
    carrinho_id: int,
    acao: str = "sucesso",
    db: Session = Depends(get_db),
):
    carrinho = (
        db.query(Carrinho)
        .filter(Carrinho.carrinho_id == carrinho_id)
        .first()
    )

    pago = carrinho and (carrinho.sitcarrinho or "").upper() != "ABERTO"

    if acao == "cancelado":
        titulo = "Pagamento cancelado"
        mensagem = (
            "O pagamento foi cancelado. Você pode voltar ao Clubbar "
            "e tentar novamente quando desejar."
        )
        icone = "↩"
        cor = "#666666"
        retorno = "cancelado"

    elif acao == "expirado":
        titulo = "Checkout expirado"
        mensagem = (
            "O tempo para pagamento expirou. "
            "Volte ao Clubbar para gerar um novo pagamento."
        )
        icone = "⌛"
        cor = "#d97706"
        retorno = "expirado"

    elif pago:
        titulo = "Pagamento confirmado!"
        mensagem = "Sua compra foi confirmada com sucesso."
        icone = "✓"
        cor = "#19a55a"
        retorno = "sucesso"

    else:
        titulo = "Pagamento em processamento"
        mensagem = (
            "Recebemos o retorno do Asaas, mas a confirmação ainda pode levar "
            "alguns segundos. Volte para o Clubbar e aguarde a atualização da sua compra."
        )
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
        h1 {{
          font-size: 24px;
        }}
        p {{
          color: #555;
          line-height: 1.5;
        }}
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