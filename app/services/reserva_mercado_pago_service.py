from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.reserva_ingresso import ReservaIngresso
from app.models.checkout_mercadopago import CheckoutMercadoPago
from app.services.mercado_pago_service import estornar_pagamento_mercado_pago
from app.services.venda_reserva_ingresso_service import finalizar_reserva_paga


async def confirmar_pagamento_reserva_mp(
    db: Session, *, checkout: CheckoutMercadoPago, pagamento: dict, access_token: str
) -> dict:
    """Emite ingresso enquanto a reserva está válida; estorna pagamento tardio."""
    reserva = db.query(ReservaIngresso).filter(
        ReservaIngresso.reserva_ingresso_id == checkout.reserva_ingresso_id
    ).populate_existing().with_for_update().first()
    if not reserva:
        raise HTTPException(409, 'Reserva do pagamento não encontrada.')
    if str(pagamento.get('status') or '').lower() != 'approved':
        raise HTTPException(409, 'Pagamento ainda não aprovado.')
    payment_id = str(pagamento.get('id') or '')
    if not payment_id:
        raise HTTPException(409, 'Pagamento sem identificador.')
    recebido = Decimal(str(pagamento.get('transaction_amount') or 0)).quantize(Decimal('0.01'))
    if recebido != Decimal(str(checkout.valor or 0)).quantize(Decimal('0.01')):
        raise HTTPException(409, 'Valor Mercado Pago divergente do checkout.')
    if checkout.status == 'REFUNDED':
        return {'ok': True, 'estornado': True}
    if checkout.venda_id:
        return {'ok': True, 'already_processed': True, 'venda_id': checkout.venda_id}
    if reserva.venda_id or reserva.sitreserva not in {'AGUARDANDO_PAGAMENTO', 'PREENCHENDO'} or reserva.dtexpiracao <= datetime.now():
        await estornar_pagamento_mercado_pago(
            access_token=access_token, payment_id=payment_id,
            venda_id=int(checkout.checkout_mercadopago_id),
        )
        checkout.payment_id = payment_id
        checkout.status = 'REFUNDED'
        if not reserva.venda_id and reserva.sitreserva in {'AGUARDANDO_PAGAMENTO', 'PREENCHENDO'}:
            reserva.sitreserva = 'EXPIRADA'
        return {'ok': True, 'estornado': True}
    return finalizar_reserva_paga(
        db, reserva_id=int(reserva.reserva_ingresso_id),
        checkout_id=int(checkout.checkout_mercadopago_id), pagamento=pagamento,
        gateway='MERCADO_PAGO', modelo_checkout=CheckoutMercadoPago,
    )
