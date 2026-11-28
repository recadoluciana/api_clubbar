from decimal import Decimal, ROUND_HALF_UP


def melhor_preco_roleta(preco_base, preco_atual, percentual):
    """Compara a roleta com o preço promocional sem acumular descontos."""
    base = Decimal(str(preco_base))
    atual = Decimal(str(preco_atual))
    desconto = Decimal(str(percentual))
    if base < 0 or atual < 0 or not 0 <= desconto <= 100:
        raise ValueError("Preço ou percentual inválido")
    premio = (base * (Decimal("1") - desconto / 100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP)
    atual = atual.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return min(atual, premio), premio < atual
