from decimal import Decimal
from datetime import datetime

def calcular_preco_final(produto):
    preco = Decimal(str(produto.vrprecoprod or 0))
    tipo = (produto.tipodesconto or "NENHUM").upper()
    desconto = Decimal(str(produto.vrdesconto or 0))
    agora = datetime.now()

    desconto_ativo_periodo = True

    if produto.dtinidesconto and agora < produto.dtinidesconto:
        desconto_ativo_periodo = False

    if produto.dtfimdesconto and agora > produto.dtfimdesconto:
        desconto_ativo_periodo = False

    if not desconto_ativo_periodo or tipo == "NENHUM" or desconto <= 0:
        return preco, False

    if tipo == "PERCENTUAL":
        preco_final = preco - (preco * desconto / Decimal("100"))
    elif tipo == "VALOR":
        preco_final = preco - desconto
    else:
        preco_final = preco

    if preco_final < 0:
        preco_final = Decimal("0.00")

    return preco_final, preco_final < preco