"""Campos financeiros fornecidos pelo Mercado Pago para o extrato."""
from decimal import Decimal, InvalidOperation


def _valor(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor))
        return float(numero) if numero.is_finite() else None
    except (InvalidOperation, ValueError, TypeError, OverflowError):
        return None


def detalhes_financeiros_pagamento(pagamento: dict) -> dict:
    detalhes = pagamento.get('transaction_details')
    detalhes = detalhes if isinstance(detalhes, dict) else {}
    tarifas = pagamento.get('fee_details')
    tarifas = tarifas if isinstance(tarifas, list) else []
    saida_tarifas = []
    for tarifa in tarifas:
        if not isinstance(tarifa, dict):
            continue
        valor = _valor(tarifa.get('amount'))
        if valor is None:
            continue
        saida_tarifas.append({
            'tipo': str(tarifa.get('type') or 'outra'),
            'valor': valor,
            'responsavel': str(tarifa.get('fee_payer') or '') or None,
        })
    parcelas = pagamento.get('installments')
    if isinstance(parcelas, bool) or not isinstance(parcelas, int) or parcelas < 1:
        parcelas = None
    return {
        'liquido_recebido': _valor(detalhes.get('net_received_amount')),
        'total_pago': _valor(detalhes.get('total_paid_amount')),
        'taxas': saida_tarifas,
        'tipo_pagamento': pagamento.get('payment_type_id'),
        'parcelas': parcelas,
        'data_liberacao': pagamento.get('money_release_date'),
        'situacao_liberacao': pagamento.get('money_release_status'),
    }
