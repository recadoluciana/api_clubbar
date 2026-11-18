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


def comparar_repasse_ingresso(pagamento: dict, valor_ingressos) -> dict:
    """Só compara pagamentos liberados, sem reembolso e com dados completos."""
    detalhes = pagamento.get('transaction_details')
    detalhes = detalhes if isinstance(detalhes, dict) else {}
    bruto = _valor(valor_ingressos)
    liquido = _valor(detalhes.get('net_received_amount'))
    estornado = _valor(pagamento.get('transaction_amount_refunded'))
    if (str(pagamento.get('status') or '').lower() != 'approved'
            or str(pagamento.get('money_release_status') or '').lower() != 'released'
            or bruto is None or liquido is None or estornado != 0):
        return {'valor_ingressos': None, 'diferenca_repasse': None}
    diferenca = Decimal(str(liquido)) - Decimal(str(bruto))
    return {'valor_ingressos': bruto, 'diferenca_repasse': float(diferenca.quantize(Decimal('0.01')))}
