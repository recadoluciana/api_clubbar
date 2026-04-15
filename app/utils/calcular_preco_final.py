from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

TZ_BR = ZoneInfo("America/Sao_Paulo")

def calcular_preco_final(produto):
    preco = Decimal(produto.vrprecoprod or 0)
    tipo = (produto.tipodesconto or "NENHUM").upper()
    desconto = Decimal(produto.vrdesconto or 0)

    agora = datetime.now(TZ_BR)

    desconto_ativo = True

    # 🔹 Ajusta datas do banco (sem timezone)
    dt_ini = produto.dtinidesconto
    dt_fim = produto.dtfimdesconto

    if dt_ini:
        dt_ini = dt_ini.replace(tzinfo=TZ_BR)
        if agora < dt_ini:
            desconto_ativo = False

    if dt_fim:
        dt_fim = dt_fim.replace(tzinfo=TZ_BR)
        if agora > dt_fim:
            desconto_ativo = False

    # 🔹 Regras de desconto
    if tipo == "NENHUM" or desconto <= 0 or not desconto_ativo:
        return float(preco), False

    if tipo == "PERCENTUAL":
        preco_final = preco - ((preco * desconto) / Decimal("100"))
    elif tipo == "VALOR":
        preco_final = preco - desconto
    else:
        preco_final = preco

    if preco_final < 0:
        preco_final = Decimal("0")

    return float(preco_final), True