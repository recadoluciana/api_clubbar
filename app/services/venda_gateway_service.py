from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.carrinho import Carrinho
from app.models.pagvenda import PagVenda
from app.models.checkout_asaas import CheckoutAsaas
from app.models.checkout_asaas_item import CheckoutAsaasItem
from app.models.itvenda import ItVenda
from app.models.itcarrinho import ItCarrinho
from app.models.loja import Loja
from app.models.venda import Venda
from app.services.carrinho_service import get_carrinho
from app.services.venda_service import (
    criar_ou_obter_venda_idempotente,
    gerar_token_qr,
)
from app.services.pagamento_status_service import set_venda_como_paga
from app.routers.pagamentos import _recalcular_itens_carrinho
from app.services.cashback_service import confirmar_uso, gerar_cashback_venda


def _finalizar_carrinho_pago(db: Session, carrinho_id: int) -> None:
    carrinho = (
        db.query(Carrinho)
        .filter(Carrinho.carrinho_id == carrinho_id)
        .with_for_update()
        .first()
    )
    if not carrinho:
        raise HTTPException(404, 'Carrinho de origem nao encontrado')
    carrinho.sitcarrinho = 'FECHADO'
    db.query(ItCarrinho).filter(
        ItCarrinho.carrinho_id == carrinho_id
    ).delete(synchronize_session=False)


def validar_confirmacao_asaas_checkout(
    db: Session,
    *,
    checkout: CheckoutAsaas,
    pagamento: dict,
    origem_confirmacao: str = 'WEBHOOK',
) -> Carrinho:
    origem = (origem_confirmacao or '').upper()
    if origem not in {'CONSULTA', 'RETORNO', 'WEBHOOK', 'RECONCILIACAO'}:
        raise HTTPException(400, 'Origem da confirmacao Asaas invalida')

    status = str(pagamento.get('status') or '').upper()
    confirmados = {'RECEIVED', 'RECEIVED_IN_CASH'}
    if not checkout.pix_qr_code_id:
        confirmados.add('CONFIRMED')
    if status not in confirmados:
        raise HTTPException(409, 'Cobranca Asaas ainda nao confirmada')

    payment_id = str(pagamento.get('id') or '').strip()
    referencia = str(pagamento.get('externalReference') or '').strip()
    referencia_esperada = str(checkout.external_reference or '').strip()
    checkout_session = str(pagamento.get('checkoutSession') or '').strip()
    checkout_esperado = str(checkout.checkout_id or '').strip()
    pix_qr_code_id = str(pagamento.get('pixQrCodeId') or '').strip()
    pix_qr_code_esperado = str(checkout.pix_qr_code_id or '').strip()
    if not payment_id:
        raise HTTPException(409, 'Pagamento Asaas sem identificador')

    if referencia and referencia_esperada and referencia != referencia_esperada:
        raise HTTPException(409, 'Referencia da cobranca Asaas divergente')
    if checkout_session and checkout_session != checkout_esperado:
        raise HTTPException(409, 'Checkout Session da cobranca Asaas divergente')
    if pix_qr_code_id and pix_qr_code_esperado and pix_qr_code_id != pix_qr_code_esperado:
        raise HTTPException(409, 'QR Code da cobranca Asaas divergente')

    identidade_confirmada = bool(
        (checkout_session and checkout_session == checkout_esperado)
        or (referencia and referencia == referencia_esperada)
        or (pix_qr_code_id and pix_qr_code_id == pix_qr_code_esperado)
    )
    if not identidade_confirmada:
        raise HTTPException(409, 'Cobranca Asaas sem vinculo com o checkout')

    valor = Decimal(str(pagamento.get('value') or 0)).quantize(Decimal('0.01'))
    esperado = Decimal(str(checkout.valor or 0)).quantize(Decimal('0.01'))
    if valor != esperado:
        raise HTTPException(409, 'Valor recebido pelo Asaas diverge da venda')

    outro = db.query(CheckoutAsaas).filter(
        CheckoutAsaas.payment_id == payment_id,
        CheckoutAsaas.checkout_asaas_id != checkout.checkout_asaas_id,
    ).first()
    if outro and outro.checkout_asaas_id != checkout.checkout_asaas_id:
        raise HTTPException(409, 'Pagamento Asaas ja vinculado a outro checkout')

    carrinho = db.query(Carrinho).filter(
        Carrinho.carrinho_id == checkout.carrinho_id
    ).first()
    loja = db.query(Loja).filter(Loja.loja_id == checkout.loja_id).first()
    if (
        not carrinho
        or not loja
        or carrinho.loja_id != checkout.loja_id
        or carrinho.cliente_id != checkout.cliente_id
        or carrinho.organizacao_id != loja.organizacao_id
    ):
        raise HTTPException(409, 'Organizacao, loja ou carrinho divergente')

    if checkout.venda_id:
        venda = db.query(Venda).filter(Venda.venda_id == checkout.venda_id).first()
        if (
            not venda
            or venda.carrinho_id != checkout.carrinho_id
            or venda.loja_id != checkout.loja_id
            or venda.organizacao_id != carrinho.organizacao_id
        ):
            raise HTTPException(409, 'Venda vinculada ao checkout e divergente')
    return carrinho


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
        carrinho_db.usuario_id,
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
    valor_pago = Decimal(str(pagamento.get('value') or 0)).quantize(
        Decimal('0.01')
    )
    valor_carrinho = Decimal(str(total_recalculado or 0)).quantize(
        Decimal('0.01')
    )
    checkout_cashback = db.query(CheckoutAsaas).filter(CheckoutAsaas.carrinho_id == carrinho_id).order_by(CheckoutAsaas.checkout_asaas_id.desc()).with_for_update().first() if gateway == "ASAAS" else None
    desconto_cashback = Decimal(str(getattr(checkout_cashback, "vrcashbackusado", 0) or 0)).quantize(Decimal("0.01"))
    if valor_pago != valor_carrinho - desconto_cashback:
        raise HTTPException(
            status_code=409,
            detail='O carrinho foi alterado. Gere uma nova tentativa de pagamento.',
        )
    fator_taxa = (valor_pago / valor_carrinho) if valor_carrinho else Decimal("1")
    if desconto_cashback > 0:
        for item in itens_recalculados:
            item["vrtaxaitvenda"] = (Decimal(str(item.get("vrtaxaitvenda") or 0)) * fator_taxa).quantize(Decimal("0.01"))
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
        usuario_id=carrinho_db.usuario_id,
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
    pag.vrpagvenda = valor_pago
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
    if checkout_cashback:
        confirmar_uso(db, checkout_cashback, venda_id)
    cashback_gerado = gerar_cashback_venda(db, venda_id)


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
        "cashback_gerado": float(cashback_gerado.vrcashback or 0)
        if cashback_gerado
        else 0.0,
    }

async def criar_venda_paga_por_checkout_snapshot(
    db: Session,
    *,
    checkout_asaas_id: int,
    gateway: str,
    pagamento: dict,
    origem_confirmacao: str = 'WEBHOOK',
):
    checkout = (
        db.query(CheckoutAsaas)
        .filter(CheckoutAsaas.checkout_asaas_id == checkout_asaas_id)
        .with_for_update(skip_locked=True)
        .first()
    )
    if not checkout:
        raise HTTPException(409, 'Checkout Asaas em processamento')
        raise HTTPException(404, "Checkout Asaas nao encontrado")
    if checkout.venda_id:
        payment_id_recebido = str(pagamento.get('id') or '').strip()
        payment_id_registrado = str(getattr(checkout, 'payment_id', None) or '').strip()
        if (
            payment_id_registrado
            and payment_id_recebido
            and payment_id_recebido != payment_id_registrado
        ):
            raise HTTPException(409, 'Pagamento diverge da venda ja processada')
        _finalizar_carrinho_pago(db, int(checkout.carrinho_id))
        return {
            "ok": True,
            "already_processed": True,
            "venda_id": int(checkout.venda_id),
        }

    validar_confirmacao_asaas_checkout(
        db,
        checkout=checkout,
        pagamento=pagamento,
        origem_confirmacao=origem_confirmacao,
    )

    itens = (
        db.query(CheckoutAsaasItem)
        .filter(CheckoutAsaasItem.checkout_asaas_id == checkout.checkout_asaas_id)
        .order_by(CheckoutAsaasItem.checkout_asaas_item_id)
        .all()
    )
    if not itens:
        raise HTTPException(409, "Checkout do Partner sem snapshot de itens")

    carrinho = db.query(Carrinho).filter(
        Carrinho.carrinho_id == checkout.carrinho_id
    ).first()
    if not carrinho:
        raise HTTPException(404, "Carrinho de origem nao encontrado")

    payment_id = str(pagamento.get("id") or "").strip()
    billing_type = str(pagamento.get("billingType") or "").upper()
    metodo = {
        "PIX": "PIX",
        "CREDIT_CARD": "CREDITO",
        "DEBIT_CARD": "DEBITO",
    }.get(billing_type, "OUTRO")
    if metodo == "OUTRO" and not checkout.pix_qr_code_id:
        metodo = "CREDITO"

    venda_existente = (
        db.query(Venda)
        .filter(Venda.carrinho_id == checkout.carrinho_id)
        .with_for_update()
        .first()
    )
    if venda_existente:
        if (
            venda_existente.organizacao_id != carrinho.organizacao_id
            or venda_existente.loja_id != checkout.loja_id
            or venda_existente.cliente_id != checkout.cliente_id
        ):
            raise HTTPException(409, 'Venda existente diverge do checkout')
        pag_existente = (
            db.query(PagVenda)
            .filter(PagVenda.venda_id == venda_existente.venda_id)
            .order_by(PagVenda.pagvenda_id.desc())
            .with_for_update()
            .first()
        )
        if not pag_existente:
            raise HTTPException(409, 'Venda existente sem pagamento')
        transacao_existente = str(pag_existente.idtransacaopagvenda or '').strip()
        if transacao_existente and payment_id and transacao_existente != payment_id:
            raise HTTPException(409, 'Venda existente pertence a outro pagamento')
        pag_existente.idtransacaopagvenda = payment_id or transacao_existente or None
        pag_existente.checkout_id = payment_id or checkout.checkout_id
        pag_existente.reference_id = checkout.external_reference
        pag_existente.provedor = (gateway or 'ASAAS').upper()
        resultado = set_venda_como_paga(
            db,
            venda_id=int(venda_existente.venda_id),
            gateway=gateway,
            payload=pagamento,
            finalizar_carrinho=False,
        )
        _finalizar_carrinho_pago(db, int(checkout.carrinho_id))
        checkout.venda_id = venda_existente.venda_id
        checkout.payment_id = payment_id or checkout.payment_id
        if not checkout.dsorigemconfirmacao:
            checkout.dsorigemconfirmacao = origem_confirmacao.upper()
            checkout.dtconfirmacao = datetime.now()
        return {
            'ok': True,
            'already_processed': True,
            'gateway': gateway,
            'carrinho_id': checkout.carrinho_id,
            'venda_id': int(venda_existente.venda_id),
            'pagvenda_id': int(pag_existente.pagvenda_id),
            'metodo_pagamento': metodo,
            'payment_id': payment_id,
            'resultado': resultado,
        }

    venda = Venda(
        organizacao_id=carrinho.organizacao_id,
        loja_id=checkout.loja_id,
        cliente_id=checkout.cliente_id,
        usuario_id=carrinho.usuario_id,
        carrinho_id=checkout.carrinho_id,
        tipovenda="PRODUTO",
        dsplataforma="ANDROID",
        sitvenda="PENDENTE",
        totalvenda=checkout.valor or 0,
    )
    db.add(venda)
    db.flush()

    for item in itens:
        for _ in range(int(item.quantidade or 1)):
            db.add(ItVenda(
                venda_id=venda.venda_id,
                tipoitem="PRODUTO",
                produto_id=item.produto_id,
                lote_id=None,
                qtitvenda=1,
                vrunititvenda=item.vrunitario,
                dsobsitvenda=item.dsobsitem,
                identregaitvenda="NAO",
                qrtokenitvenda=gerar_token_qr(),
                nmparticipante=item.nmparticipante,
                cpfparticipante=item.cpfparticipante,
                pctaxaitvenda=item.pctaxaitvenda,
                vrtaxaitvenda=item.vrtaxaitvenda,
            ))

    pag = PagVenda(
        venda_id=venda.venda_id,
        dsmetodopag=metodo,
        vrpagvenda=checkout.valor or 0,
        sitpagvenda="PENDENTE",
        idtransacaopagvenda=payment_id or None,
        provedor=(gateway or "ASAAS").upper(),
        reference_id=checkout.external_reference,
        checkout_id=payment_id or checkout.checkout_id,
    )
    db.add(pag)
    db.flush()

    resultado = set_venda_como_paga(
        db,
        venda_id=int(venda.venda_id),
        gateway=gateway,
        payload=pagamento,
        finalizar_carrinho=True,
    )
    checkout.venda_id = venda.venda_id
    checkout.payment_id = payment_id or checkout.payment_id
    checkout.dsorigemconfirmacao = origem_confirmacao.upper()
    checkout.dtconfirmacao = datetime.now()

    return {
        "ok": True,
        "gateway": gateway,
        "carrinho_id": checkout.carrinho_id,
        "venda_id": int(venda.venda_id),
        "pagvenda_id": int(pag.pagvenda_id),
        "metodo_pagamento": metodo,
        "payment_id": payment_id,
        "resultado": resultado,
    }
