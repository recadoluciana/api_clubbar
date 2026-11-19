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
    # A taxa de antecipação pode aparecer somente em charges_details. Não
    # reproduza os demais itens de charges_details: eles também podem estar em
    # fee_details, incluindo a comissão do marketplace e a tarifa principal.
    tipos_informados = {tarifa['tipo'] for tarifa in saida_tarifas}
    encargos = pagamento.get('charges_details')
    if 'financed_advance_fee' not in tipos_informados and isinstance(encargos, list):
        for encargo in encargos:
            if not isinstance(encargo, dict) or encargo.get('type') != 'fee' or encargo.get('name') != 'financed_advance_fee':
                continue
            valores = encargo.get('amounts') if isinstance(encargo.get('amounts'), dict) else {}
            valor = _valor(valores.get('original'))
            estornado = _valor(valores.get('refunded'))
            if valor is None or estornado != 0:
                continue
            contas = encargo.get('accounts') if isinstance(encargo.get('accounts'), dict) else {}
            saida_tarifas.append({
                'tipo': 'financed_advance_fee',
                'valor': valor,
                'responsavel': str(contas.get('from') or '') or None,
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


def resumir_vendas_pagamentos(pagamentos) -> dict:
    """Totais dos pagamentos aprovados identificados para a loja e conta."""
    bruto = Decimal('0')
    liquido = Decimal('0')
    bruto_disponivel = True
    liquido_disponivel = True
    parcial = False
    for pagamento in pagamentos:
        if str(pagamento.get('status') or '').lower() != 'approved':
            continue
        valor = _valor(pagamento.get('transaction_amount'))
        detalhes = pagamento.get('transaction_details')
        detalhes = detalhes if isinstance(detalhes, dict) else {}
        valor_liquido = _valor(detalhes.get('net_received_amount'))
        reembolso = _valor(pagamento.get('transaction_amount_refunded'))
        if valor is None:
            bruto_disponivel = False
        else:
            bruto += Decimal(str(valor))
        if reembolso is not None and reembolso > 0:
            parcial = True
        if valor_liquido is None or reembolso is None or reembolso != 0:
            liquido_disponivel = False
        else:
            liquido += Decimal(str(valor_liquido))
    return {
        'bruto': float(bruto.quantize(Decimal('0.01'))) if bruto_disponivel else None,
        'liquido': float(liquido.quantize(Decimal('0.01'))) if liquido_disponivel else None,
        'reembolso_parcial': parcial,
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
