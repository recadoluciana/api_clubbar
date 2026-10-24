from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.core.config import MERCADO_PAGO_WEBHOOK_SECRET
from app.models.checkout_mercadopago import CheckoutMercadoPago
from app.models.lojamercadopago import LojaMercadoPago
from app.models.reserva_ingresso import ReservaIngresso
from app.services.mercado_pago_service import buscar_pagamento_por_id, obter_token_loja
from app.services.venda_gateway_service import criar_venda_paga_por_carrinho_gateway
from app.services.venda_reserva_ingresso_service import finalizar_reserva_paga
from app.routers.pagamentos import _notificar_confirmacao_mercado_pago


router = APIRouter(tags=["Webhook Mercado Pago"])


def _assinatura_valida(request: Request, payment_id: str) -> bool:
    """Valida HMAC oficial quando a assinatura secreta foi configurada."""
    if not MERCADO_PAGO_WEBHOOK_SECRET:
        # A confirmação ainda consulta a API autenticada do vendedor; a
        # assinatura passa a ser obrigatória assim que o segredo for informado.
        return True
    assinatura = request.headers.get('x-signature', '')
    partes = dict(
        parte.strip().split('=', 1)
        for parte in assinatura.split(',')
        if '=' in parte
    )
    ts, recebida = partes.get('ts'), partes.get('v1')
    if not ts or not recebida:
        return False
    request_id = request.headers.get('x-request-id', '')
    manifest = f'id:{payment_id};request-id:{request_id};ts:{ts};'
    esperada = hmac.new(
        MERCADO_PAGO_WEBHOOK_SECRET.encode(),
        manifest.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(esperada, recebida)


@router.post('/mercado-pago/webhook', include_in_schema=False)
async def receber_webhook_mercado_pago(request: Request):
    """Confirma somente após consultar o pagamento na API do Mercado Pago.

    O conteúdo da notificação não é suficiente para concluir uma venda; ele
    apenas informa qual pagamento consultar com o token OAuth da própria loja.
    """
    try:
        corpo = await request.json()
    except Exception:
        corpo = {}
    tipo = str(corpo.get('type') or request.query_params.get('type') or '').lower()
    payment_id = str(
        (corpo.get('data') or {}).get('id') or request.query_params.get('data.id') or ''
    ).strip()
    user_id = str(corpo.get('user_id') or request.query_params.get('user_id') or '').strip()
    if tipo not in {'payment', 'payments'} or not payment_id or not user_id:
        return {'ok': True, 'ignorado': True}
    if not _assinatura_valida(request, payment_id):
        raise HTTPException(401, 'Assinatura do webhook Mercado Pago inválida.')

    db: Session = SessionLocal()
    try:
        configuracao = db.query(LojaMercadoPago).filter(
            LojaMercadoPago.mercadopago_user_id == user_id,
            LojaMercadoPago.statusintegracao == 'ATIVA',
        ).first()
        if not configuracao:
            return {'ok': True, 'ignorado': True}
        token, _ = await obter_token_loja(db, int(configuracao.loja_id))
        pagamento = await buscar_pagamento_por_id(access_token=token, payment_id=payment_id)
        if not pagamento or str(pagamento.get('status') or '').lower() != 'approved':
            return {'ok': True, 'pendente': True}
        referencia = str(pagamento.get('external_reference') or '')
        checkout = db.query(CheckoutMercadoPago).filter(
            CheckoutMercadoPago.external_reference == referencia,
            CheckoutMercadoPago.loja_id == configuracao.loja_id,
        ).with_for_update().first()
        if not checkout:
            return {'ok': True, 'ignorado': True}
        recebido = Decimal(str(pagamento.get('transaction_amount') or 0)).quantize(Decimal('0.01'))
        esperado = Decimal(str(checkout.valor or 0)).quantize(Decimal('0.01'))
        if recebido != esperado:
            raise HTTPException(409, 'Valor Mercado Pago divergente do checkout.')
        if checkout.venda_id:
            _notificar_confirmacao_mercado_pago(db, checkout)
            return {'ok': True, 'venda_id': checkout.venda_id}

        if checkout.reserva_ingresso_id:
            resultado = finalizar_reserva_paga(
                db,
                reserva_id=int(checkout.reserva_ingresso_id),
                checkout_id=int(checkout.checkout_mercadopago_id),
                pagamento=pagamento,
                gateway='MERCADO_PAGO',
                modelo_checkout=CheckoutMercadoPago,
            )
        else:
            resultado = await criar_venda_paga_por_carrinho_gateway(
                db,
                carrinho_id=int(checkout.carrinho_id),
                gateway='MERCADO_PAGO',
                pagamento={
                    **pagamento,
                    'value': float(recebido),
                    'externalReference': checkout.external_reference,
                },
                checkout_origem=checkout,
            )
        checkout.payment_id = payment_id
        checkout.status = 'APPROVED'
        checkout.venda_id = resultado.get('venda_id')
        checkout.dsorigemconfirmacao = 'WEBHOOK'
        checkout.dtconfirmacao = datetime.now()
        db.commit()
        _notificar_confirmacao_mercado_pago(db, checkout)
        return {'ok': True, 'venda_id': checkout.venda_id}
    except HTTPException:
        db.rollback()
        raise
    except Exception as erro:
        db.rollback()
        raise HTTPException(500, 'Falha ao processar webhook Mercado Pago.') from erro
    finally:
        db.close()
