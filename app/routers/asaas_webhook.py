import traceback
import hmac
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.carrinho import Carrinho
from app.services.venda_gateway_service import (
    criar_venda_paga_por_carrinho_gateway,
    criar_venda_paga_por_checkout_snapshot,
    validar_confirmacao_asaas_checkout,
)

from app.models.checkout_asaas import CheckoutAsaas
from app.models.checkout_asaas_item import CheckoutAsaasItem
from app.models.checkout_asaas_pagador import CheckoutAsaasPagador
from app.models.cliente import Cliente
from app.models.cobrancaimplantacao import CobrancaImplantacao
from app.services.implantacao_service import reconciliar_cobranca_implantacao
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


def evento_confirma_pagamento_asaas(evento: str, status: str, *, pix_direto: bool) -> bool:
    if pix_direto:
        # Para Pix, PAYMENT_CONFIRMED pode representar analise cautelar. A
        # liberacao ocorre apenas quando o Asaas informa o recebimento.
        return evento == "PAYMENT_RECEIVED" or status == "RECEIVED"
    return evento in {"PAYMENT_RECEIVED", "PAYMENT_CONFIRMED", "CHECKOUT_PAID"} or status in {
        "RECEIVED",
        "CONFIRMED",
        "PAID",
    }


def _somente_digitos(valor: object) -> str:
    return "".join(char for char in str(valor or "") if char.isdigit())


def registrar_pagador_asaas(
    db: Session,
    checkout: CheckoutAsaas,
    customer: dict,
    payment_id: str | None,
) -> CheckoutAsaasPagador:
    pagador = (
        db.query(CheckoutAsaasPagador)
        .filter(CheckoutAsaasPagador.checkout_asaas_id == checkout.checkout_asaas_id)
        .first()
    )
    if not pagador:
        pagador = CheckoutAsaasPagador(checkout_asaas_id=checkout.checkout_asaas_id)
        db.add(pagador)

    pagador.venda_id = checkout.venda_id
    pagador.payment_id = str(payment_id) if payment_id else pagador.payment_id
    pagador.asaas_customer_id = str(customer.get("id") or "") or None
    pagador.nome = customer.get("name")
    pagador.cpf_cnpj = _somente_digitos(customer.get("cpfCnpj")) or None
    pagador.email = customer.get("email")
    pagador.telefone = customer.get("mobilePhone") or customer.get("phone")
    pagador.endereco = customer.get("address")
    pagador.numero = customer.get("addressNumber")
    pagador.complemento = customer.get("complement")
    pagador.bairro = customer.get("province")
    pagador.cep = customer.get("postalCode")
    pagador.cidade = customer.get("city")
    pagador.uf = customer.get("state")
    return pagador

def atualizar_cliente_com_customer_asaas(
    db: Session,
    cliente: Cliente,
    customer: dict,
) -> None:
    # O cliente padrão do caixa é compartilhado entre consumidores e nunca
    # deve receber dados pessoais da conta que efetuou um pagamento.
    if str(cliente.cliente_padrao or "N").upper() == "S":
        return

    cpf = _somente_digitos(customer.get("cpfCnpj"))
    if cpf:
        cpf_em_uso = (
            db.query(Cliente.cliente_id)
            .filter(
                Cliente.nrcpfcliente == cpf,
                Cliente.cliente_id != cliente.cliente_id,
            )
            .first()
        )
        if not cpf_em_uso:
            cliente.nrcpfcliente = cpf

    cliente.nrtelcliente = (
        customer.get("mobilePhone")
        or customer.get("phone")
        or cliente.nrtelcliente
    )
    cliente.endcliente = customer.get("address") or cliente.endcliente
    cliente.nrendcliente = customer.get("addressNumber") or cliente.nrendcliente
    cliente.complcliente = customer.get("complement") or cliente.complcliente
    cliente.bairrocliente = customer.get("province") or cliente.bairrocliente
    cliente.cepcliente = customer.get("postalCode") or cliente.cepcliente
    cliente.cidadecliente = customer.get("city") or cliente.cidadecliente
    cliente.ufcliente = customer.get("state") or cliente.ufcliente

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

    payment_implantacao = body.get("payment") or body.get("checkout") or {}
    checkout_implantacao = (
        payment_implantacao.get("checkoutSession")
        or body.get("checkoutId")
        or body.get("checkoutSession")
    )
    referencia_implantacao = str(
        payment_implantacao.get("externalReference")
        or body.get("externalReference")
        or ""
    ).strip()
    cobranca_implantacao = None
    if checkout_implantacao:
        cobranca_implantacao = db.query(CobrancaImplantacao).filter(
            CobrancaImplantacao.asaas_checkout_id == str(checkout_implantacao)
        ).first()
    if not cobranca_implantacao and referencia_implantacao.startswith("IMPLANTACAO-"):
        cobranca_implantacao = db.query(CobrancaImplantacao).filter(
            CobrancaImplantacao.external_reference == referencia_implantacao
        ).first()
    if cobranca_implantacao:
        cobranca_implantacao = await reconciliar_cobranca_implantacao(
            db, cobranca_implantacao
        )
        return {
            "ok": True,
            "tipo": "IMPLANTACAO",
            "status": cobranca_implantacao.status,
        }

    print('[ASAAS WEBHOOK][NAO PROCESSADO]', body.get('event'))
    return {
        'ok': True,
        'ignored': True,
        'reason': 'Confirmacao realizada somente por retorno ou consulta',
    }

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

        pix_direto = bool(registro_checkout.pix_qr_code_id)
        if not evento_confirma_pagamento_asaas(
            evento,
            status,
            pix_direto=pix_direto,
        ):
            if registro_checkout:
                # Estados intermediarios do Asaas nao liberam nem concluem
                # a tentativa local; apenas guardamos o payment_id.
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
        if pix_direto and valor_recebido != valor_esperado:
            raise HTTPException(
                status_code=409,
                detail="Valor recebido pelo Asaas diverge da venda",
            )

        print("[ASAAS WEBHOOK] criando venda carrinho:", carrinho_id)

        validar_confirmacao_asaas_checkout(
            db,
            checkout=registro_checkout,
            pagamento=payment,
            origem_confirmacao='WEBHOOK',
        )
        if not registro_checkout.dsorigemconfirmacao:
            registro_checkout.dsorigemconfirmacao = 'WEBHOOK'
            registro_checkout.dtconfirmacao = datetime.now()

        possui_snapshot = db.query(CheckoutAsaasItem).filter(
            CheckoutAsaasItem.checkout_asaas_id
            == registro_checkout.checkout_asaas_id
        ).first() is not None
        if possui_snapshot:
            resultado = await criar_venda_paga_por_checkout_snapshot(
                db,
                checkout_asaas_id=registro_checkout.checkout_asaas_id,
                origem_confirmacao='WEBHOOK',
                gateway="ASAAS",
                pagamento=payment,
            )
        else:
            resultado = await criar_venda_paga_por_carrinho_gateway(
                db,
                carrinho_id=carrinho_id,
                gateway="ASAAS",
                pagamento=payment,
                metodo_pagamento=None,
            )
        venda_id = resultado.get("venda_id")
        if venda_id:
            registro_checkout.venda_id = int(venda_id)

        customer_id = payment.get("customer")

        if customer_id and registro_checkout and ASAAS_API_KEY:
            customer = await buscar_customer_asaas(str(customer_id), ASAAS_API_KEY)
            registrar_pagador_asaas(db, registro_checkout, customer, payment_id)

            cliente = (
                db.query(Cliente)
                .filter(Cliente.cliente_id == registro_checkout.cliente_id)
                .first()
            )

            if cliente:
                atualizar_cliente_com_customer_asaas(db, cliente, customer)
        if registro_checkout:
            registro_checkout.status = "PAID"
            if payment_id:
                registro_checkout.payment_id = str(payment_id)
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

    except HTTPException as e:
        db.rollback()
        print('[ASAAS WEBHOOK][IGNORADO]', e.status_code, e.detail)
        if e.status_code >= 500:
            raise
        return {
            'ok': True,
            'ignored': True,
            'event': evento,
            'status': status,
            'reason': str(e.detail),
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
    carrinho_id: int | None = None,
    reserva_ingresso_id: int | None = None,
    acao: str = "sucesso",
    origem: str = "CLIENT",
    db: Session = Depends(get_db),
):
    if (carrinho_id is None) == (reserva_ingresso_id is None):
        raise HTTPException(400, "Retorno sem origem de compra válida")
    if carrinho_id is not None:
        db.query(Carrinho).filter(Carrinho.carrinho_id == carrinho_id).first()

    checkout_registrado = (
        db.query(CheckoutAsaas)
        .filter(
            CheckoutAsaas.reserva_ingresso_id == reserva_ingresso_id
            if reserva_ingresso_id is not None
            else CheckoutAsaas.carrinho_id == carrinho_id
        )
        .order_by(CheckoutAsaas.checkout_asaas_id.desc())
        .first()
    )
    checkout_id_retorno = getattr(checkout_registrado, "checkout_id", "") if checkout_registrado else ""
    if (
        acao == "sucesso"
        and checkout_registrado
        and not getattr(checkout_registrado, "venda_id", None)
    ):
        try:
            if reserva_ingresso_id is not None:
                from app.routers.reservas_ingressos import status_reserva
                await status_reserva(reserva_ingresso_id, checkout_registrado.cliente_id, db)
            else:
                from app.routers.pagamentos import status_checkout_asaas
                await status_checkout_asaas(checkout_registrado.checkout_id, db)
            db.refresh(checkout_registrado)
        except Exception as exc:
            if hasattr(db, "rollback"):
                db.rollback()
            print('[ASAAS RETORNO][CONSULTA PENDENTE]', repr(exc))
            checkout_registrado = (
                db.query(CheckoutAsaas)
                .filter(
                    CheckoutAsaas.reserva_ingresso_id == reserva_ingresso_id
                    if reserva_ingresso_id is not None
                    else CheckoutAsaas.carrinho_id == carrinho_id
                )
                .order_by(CheckoutAsaas.checkout_asaas_id.desc())
                .first()
            )
    pago = bool(
        checkout_registrado
        and checkout_registrado.venda_id
        and (checkout_registrado.status or "").upper()
        in {"PAID", "RECEIVED", "CONFIRMED"}
    )
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
