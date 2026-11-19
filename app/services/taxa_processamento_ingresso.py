from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from fastapi import HTTPException

CENTAVOS = Decimal('0.01')
TAXAS_PROCESSAMENTO = {'PIX': Decimal('0.0099'), 'CREDIT_CARD': Decimal('0.0499')}
TAXA_PROCESSAMENTO_CLIENTE = Decimal('0.02')


def cotar_ingressos_mercado_pago(valor_unitario: Decimal, taxa_unitaria: Decimal, quantidade: int, metodo: str) -> dict:
    metodo = str(metodo or '').upper()
    if metodo == 'CREDITO':
        metodo = 'CREDIT_CARD'
    percentual_mp = TAXAS_PROCESSAMENTO.get(metodo)
    valor_unitario = Decimal(str(valor_unitario)).quantize(CENTAVOS)
    taxa_unitaria = Decimal(str(taxa_unitaria)).quantize(CENTAVOS)
    if percentual_mp is None or valor_unitario <= 0 or taxa_unitaria < 0 or quantidade <= 0:
        raise HTTPException(422, 'Não foi possível calcular a taxa para esse pagamento.')
    valor_ingressos = valor_unitario * quantidade
    conveniencia = taxa_unitaria * quantidade
    # Arredonda cada ingresso antes de multiplicar, como a taxa de conveniência.
    processamento_unitario = (valor_unitario * TAXA_PROCESSAMENTO_CLIENTE).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    processamento = processamento_unitario * quantidade
    subtotal = valor_ingressos + conveniencia
    total = subtotal + processamento
    tarifa_mp = (total * percentual_mp).quantize(CENTAVOS, rounding=ROUND_CEILING)
    # O Mercado Pago não aceita comissão negativa. Não impedimos a venda:
    # nesse caso, a diferença no líquido do parceiro precisará de conciliação.
    comissao = max(Decimal('0.00'), conveniencia + processamento - tarifa_mp)
    return {'metodo': metodo, 'ingressos': valor_ingressos, 'conveniencia': conveniencia,
            'subtotal': subtotal, 'processamento': processamento, 'total': total,
            'tarifa_mp_estimada': tarifa_mp, 'comissao_clubbar': comissao}


def cotar_itens_mercado_pago(itens, metodo: str) -> dict:
    """Cota uma transação com modalidades distintas, arredondando por ingresso."""
    metodo = 'CREDIT_CARD' if str(metodo).upper() == 'CREDITO' else str(metodo).upper()
    if metodo not in TAXAS_PROCESSAMENTO: raise HTTPException(422, 'Método de pagamento inválido.')
    ingressos = conveniencia = processamento = Decimal('0')
    quantidade = 0
    for item in itens:
        qtd = int(item.qtreservada)
        unit = Decimal(str(item.vrunitario)).quantize(CENTAVOS)
        taxa = Decimal(str(item.vrtaxa)).quantize(CENTAVOS)
        ingressos += unit * qtd; conveniencia += taxa * qtd; quantidade += qtd
        processamento += (unit * TAXA_PROCESSAMENTO_CLIENTE).quantize(CENTAVOS, rounding=ROUND_HALF_UP) * qtd
    subtotal = ingressos + conveniencia
    total = subtotal + processamento
    tarifa = (total * TAXAS_PROCESSAMENTO[metodo]).quantize(CENTAVOS, rounding=ROUND_CEILING)
    return {'metodo': metodo, 'ingressos': ingressos, 'conveniencia': conveniencia,
            'subtotal': subtotal, 'processamento': processamento, 'total': total,
            'tarifa_mp_estimada': tarifa, 'comissao_clubbar': max(Decimal('0'), conveniencia + processamento - tarifa),
            'quantidade': quantidade}


def distribuir_processamento(valor: Decimal, quantidade: int) -> list[Decimal]:
    valor = Decimal(str(valor)).quantize(CENTAVOS)
    if quantidade <= 0 or valor < 0:
        raise HTTPException(409, 'Valores do pagamento de ingresso divergentes.')
    centavos = int(valor * 100)
    parte, resto = divmod(centavos, quantidade)
    return [Decimal(parte + (1 if indice < resto else 0)) / 100 for indice in range(quantidade)]
