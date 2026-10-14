from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

TZ_BR = ZoneInfo("America/Sao_Paulo")

def calcular_preco_final(item_cardapio):
    """Calcula preço a partir do item do cardápio, nunca do produto mestre."""
    preco = Decimal(item_cardapio.vrpreco or 0)
    tipo = (item_cardapio.tipodesconto or "NENHUM").upper()
    desconto = Decimal(item_cardapio.vrdesconto or 0)

    agora = datetime.now(TZ_BR)

    desconto_ativo = True

    # 🔹 Ajusta datas do banco (sem timezone)
    dt_ini = item_cardapio.dtinidesconto
    dt_fim = item_cardapio.dtfimdesconto

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
