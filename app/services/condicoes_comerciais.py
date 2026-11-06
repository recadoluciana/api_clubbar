from decimal import Decimal, InvalidOperation

from fastapi import HTTPException


def condicoes_comerciais(modalidade: str, mensalidade: object | None) -> tuple[str, Decimal | None]:
    """Valida a modalidade e devolve o texto a ser incluído no contrato."""
    if modalidade == "EXPERIENCIA":
        if mensalidade is not None:
            raise HTTPException(422, "A mensalidade será negociada após o período gratuito.")
        texto = (
            "Os primeiros três meses de uso da plataforma são gratuitos, contados a partir da assinatura. "
            "Após esse prazo, a mensalidade será negociada entre as partes conforme o faturamento; "
            "nenhuma cobrança automática será iniciada sem acordo posterior."
        )
        return texto, None
    if modalidade != "MENSALIDADE":
        raise HTTPException(422, "Selecione a modalidade comercial do contrato.")
    try:
        valor = Decimal(str(mensalidade))
        if not valor.is_finite() or valor <= 0 or valor > Decimal("99999999.99") or valor.as_tuple().exponent < -2:
            raise ValueError
    except (InvalidOperation, TypeError, ValueError):
        raise HTTPException(422, "Informe uma mensalidade válida e maior que zero.")
    formatado = f"{valor:.2f}".replace(".", ",")
    return f"A mensalidade negociada desde o início da parceria é de R$ {formatado}.", valor
