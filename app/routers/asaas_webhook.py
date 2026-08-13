import traceback
import hmac
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.carrinho import Carrinho
from app.services.venda_gateway_service import criar_venda_paga_por_carrinho_gateway

from app.models.checkout_asaas import CheckoutAsaas
from app.models.cliente import Cliente
from app.services.asaas_service import buscar_customer_asaas
from app.services.repasse_service import criar_repasse_da_venda
from app.core.config import (
    ASAAS_API_KEY,
    ASAAS_WEBHOOK_TOKEN,
    PUBLIC_CLIENT_BASE_URL,
    PUBLIC_PARTNER_BASE_URL,
)

router = APIRouter(
    prefix="/asaas",
    tags=["Asaas"],
)


def validar_token_webhook_asaas(
    token_recebido: str | None,
) -> None:
    if not ASAAS_WEBHOOK_TOKEN or not token_recebido:
        raise HTTPException(status_code=401, detail="Webhook Asaas não autorizado")
    if not hmac.compare_digest(token_recebido, ASAAS_WEBHOOK_TOKEN):
        raise HTTPException(status_code=401, detail="Webhook Asaas não autorizado")


@router.post("/webhook")
async def asaas_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    validar_token_webhook_asaas(request.headers.get("asaas-access-token"))

    try:
        body = await request.json()
    except Exception:
        body = {}

    try:
        evento = str(body.get("event") or "").upper()

        checkout = body.get("checkout") or {}
        payment = body.get("payment") or checkout or body.get("object") or {}

        status = str(payment.get("status") or body.get("status") or "").upper()

        checkout_id = (
            payment.get("checkoutSession")
            or checkout.get("id")
            or body.get("checkoutId")
            or body.get("checkoutSession")
        )
        payment_id = payment.get("id") or body.get("paymentId")
        pix_qr_code_id = payment.get("pixQrCodeId") or body.get("pixQrCodeId")

        print(
            "[ASAAS WEBHOOK]",
            "event=", evento,
            "checkout_id=", checkout_id,
            "payment_id=", payment_id,
        )

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

        if not registro_checkout and external_reference:
            registro_checkout = (
                db.query(CheckoutAsaas)
                .filter(CheckoutAsaas.external_reference == external_reference)
                .order_by(CheckoutAsaas.checkout_asaas_id.desc())
                .first()
            )

        if not registro_checkout and pix_qr_code_id:
            registro_checkout = (
                db.query(CheckoutAsaas)
                .filter(CheckoutAsaas.pix_qr_code_id == str(pix_qr_code_id))
                .first()
            )

        if not registro_checkout:
            return {
                "ok": True,
                "ignored": True,
                "msg": "Checkout não pertence a este ambiente",
                "event": evento,
                "status": status,
                "checkout_id": checkout_id,
                "payment_id": payment_id,
                "externalReference": external_reference,
            }

        carrinho_id = int(registro_checkout.carrinho_id)
        referencia_registrada = str(registro_checkout.external_reference or "").strip()
        if external_reference and referencia_registrada and external_reference != referencia_registrada:
            return {
                "ok": True,
                "ignored": True,
                "msg": "Referência do checkout divergente",
                "event": evento,
                "checkout_id": checkout_id,
                "payment_id": payment_id,
            }

        external_reference = referencia_registrada or external_reference

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

        pix_direto = bool(registro_checkout.pix_qr_code_id)
        evento_confirma = (
            evento == "PAYMENT_RECEIVED"
            if pix_direto
            else evento in eventos_confirmados
        )
        status_confirma = (
            status == "RECEIVED"
            if pix_direto
            else status in status_confirmados
        )

        if not evento_confirma and not status_confirma:
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

        valor_recebido = Decimal(str(payment.get("value") or 0)).quantize(Decimal("0.01"))
        valor_esperado = Decimal(str(registro_checkout.valor or 0)).quantize(Decimal("0.01"))
        if valor_recebido != valor_esperado:
            raise HTTPException(
                status_code=409,
                detail="Valor recebido pelo Asaas diverge da venda",
            )

        print("[ASAAS WEBHOOK] criando venda carrinho:", carrinho_id)

        resultado = await criar_venda_paga_por_carrinho_gateway(
            db,
            carrinho_id=carrinho_id,
            gateway="ASAAS",
            pagamento=payment,
            metodo_pagamento=None,
        )

        customer_id = payment.get("customer")

        if customer_id and registro_checkout and ASAAS_API_KEY:
            customer = await buscar_customer_asaas(str(customer_id), ASAAS_API_KEY)

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
                
        if registro_checkout:
            registro_checkout.status = "PAID"
            if payment_id:
                registro_checkout.payment_id = str(payment_id)
            venda_id = resultado.get("venda_id")
            if venda_id:
                criar_repasse_da_venda(
                    db,
                    venda_id=int(venda_id),
                    checkout=registro_checkout,
                )

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

        raise HTTPException(
            status_code=500,
            detail="Erro ao processar webhook Asaas",
        ) from e


@router.get("/retorno", response_class=HTMLResponse)
async def asaas_retorno(
    carrinho_id: int,
    acao: str = "sucesso",
    origem: str = "CLIENT",
    db: Session = Depends(get_db),
):
    carrinho = (
        db.query(Carrinho)
        .filter(Carrinho.carrinho_id == carrinho_id)
        .first()
    )

    pago = carrinho and (carrinho.sitcarrinho or "").upper() != "ABERTO"
    checkout_registrado = (
        db.query(CheckoutAsaas)
        .filter(CheckoutAsaas.carrinho_id == carrinho_id)
        .order_by(CheckoutAsaas.checkout_asaas_id.desc())
        .first()
    )
    checkout_id_retorno = checkout_registrado.checkout_id if checkout_registrado else ""
    origem_normalizada = origem.strip().upper()
    url_retorno = (
        PUBLIC_PARTNER_BASE_URL
        if origem_normalizada == "PARTNER"
        else PUBLIC_CLIENT_BASE_URL
    ) or "/"

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

        <a href="{url_retorno}?pagamento={retorno}&gateway=asaas&checkout_id={checkout_id_retorno}">
          Voltar para o Clubbar
        </a>

      </div>
    </body>
    </html>
    """
