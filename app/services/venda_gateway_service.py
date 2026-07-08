from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.carrinho import Carrinho
from app.models.pagvenda import PagVenda
from app.models.checkout_asaas import CheckoutAsaas
from app.services.carrinho_service import get_carrinho
from app.services.venda_service import criar_ou_obter_venda_idempotente
from app.services.pagamento_status_service import set_venda_como_paga
from app.routers.pagamentos import _recalcular_itens_carrinho


async def criar_venda_paga_por_carrinho_gateway(
    db: Session,
    *,
    carrinho_id: int,
    gateway: str,
    pagamento: dict,
    metodo_pagamento: str | None = None,
):
    gateway = (gateway or "").upper()

    carrinho_db = (
        db.query(Carrinho)
        .filter(Carrinho.carrinho_id == carrinho_id)
        .with_for_update()
        .first()
    )

    if not carrinho_db:
        print(f"[{gateway} WEBHOOK] Carrinho não encontrado:", carrinho_id)
        return {
            "ok": True,
            "msg": "Carrinho não encontrado",
            "carrinho_id": carrinho_id,
        }

    if (carrinho_db.sitcarrinho or "").upper() != "ABERTO":
        print(f"[{gateway} WEBHOOK] Carrinho já fechado:", carrinho_id)
        return {
            "ok": True,
            "msg": "Carrinho já fechado",
            "carrinho_id": carrinho_id,
        }

    carrinho = get_carrinho(
        db,
        carrinho_db.cliente_id,
        carrinho_db.loja_id,
    )

    if not carrinho:
        raise HTTPException(status_code=404, detail="Carrinho não encontrado")

    itens = carrinho.get("itens") or []

    if not itens:
        raise HTTPException(status_code=400, detail="Carrinho vazio")

    print("antes de recalcular itens >>>>>>>>>>>", itens)
    itens_recalculados, total_recalculado = _recalcular_itens_carrinho(
        db,
        itens,
    )
    print("depois de recalcular itens >>>>>>>>>>>", itens_recalculados)

    payment_id = str(pagamento.get("id") or "").strip()
    external_reference = str(pagamento.get("externalReference") or "").strip()

    payment_type_id = str(pagamento.get("payment_type_id") or "").lower()
    payment_method_id = str(pagamento.get("payment_method_id") or "").lower()
    billing_type = str(pagamento.get("billingType") or "").upper()

    if not metodo_pagamento:
        if gateway == "ASAAS":
            if billing_type == "CREDIT_CARD":
                metodo_pagamento = "CREDITO"
            elif billing_type == "DEBIT_CARD":
                metodo_pagamento = "DEBITO"
            elif billing_type == "PIX":
                metodo_pagamento = "PIX"
            else:
                metodo_pagamento = "OUTRO"
        else:
            if payment_type_id == "credit_card":
                metodo_pagamento = "CREDITO"
            elif payment_type_id == "debit_card":
                metodo_pagamento = "DEBITO"
            elif payment_method_id == "pix" or payment_type_id in {
                "bank_transfer",
                "account_money",
            }:
                metodo_pagamento = "PIX"
            else:
                metodo_pagamento = "OUTRO"

    chave_idempotente = (
        payment_id
        or external_reference
        or f"{gateway}-CARRINHO-{carrinho_id}"
    )

    venda = await criar_ou_obter_venda_idempotente(
        db,
        cliente_id=carrinho_db.cliente_id,
        organizacao_id=carrinho_db.organizacao_id,
        loja_id=carrinho_db.loja_id,
        carrinho={
            **carrinho,
            "total": total_recalculado,
            "itens": itens_recalculados,
        },
        chave=chave_idempotente,
        metodo_pagamento=metodo_pagamento,
    )

    venda_id = int(venda["venda_id"])
    pagvenda_id = int(venda["pagvenda_id"])

    pag = (
        db.query(PagVenda)
        .filter(PagVenda.pagvenda_id == pagvenda_id)
        .with_for_update()
        .first()
    )

    if not pag:
        raise HTTPException(status_code=404, detail="PagVenda não encontrada")

    pag.dsmetodopag = metodo_pagamento
    pag.sitpagvenda = "PAGO"
    pag.idtransacaopagvenda = payment_id or external_reference
    pag.checkout_id = payment_id or external_reference
    pag.reference_id = external_reference or str(venda_id)
    pag.pay_url = None
    pag.provedor = gateway

    if gateway == "ASAAS":
        checkout = (
            db.query(CheckoutAsaas)
            .filter(CheckoutAsaas.carrinho_id == carrinho_id)
            .order_by(CheckoutAsaas.checkout_asaas_id.desc())
            .first()
        )

        if checkout:
            checkout.payment_id = payment_id or checkout.payment_id
            checkout.status = str(
                pagamento.get("status")
                or checkout.status
                or "CONFIRMED"
            )

    resultado = set_venda_como_paga(
        db,
        venda_id=venda_id,
        gateway=gateway,
        payload=pagamento,
    )

    carrinho_db.idpixmercadopago = None
    carrinho_db.vrpixmercadopago = None

    return {
        "ok": True,
        "gateway": gateway,
        "carrinho_id": carrinho_id,
        "venda_id": venda_id,
        "pagvenda_id": pagvenda_id,
        "metodo_pagamento": metodo_pagamento,
        "payment_id": payment_id,
        "external_reference": external_reference,
        "resultado": resultado,
    }