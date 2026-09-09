from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.taxapadrao import TaxaPadrao


CENTAVOS = Decimal("0.01")


def taxa_padrao_vigente(db: Session) -> TaxaPadrao:
    taxa = db.query(TaxaPadrao).filter(TaxaPadrao.sittaxapadrao == "VIGENTE").order_by(
        TaxaPadrao.nrversao.desc()
    ).first()
    if not taxa:
        raise HTTPException(422, "Nenhuma versão de taxas padrão está vigente")
    return taxa


def calcular_taxa_ingresso_unitaria(valor: Decimal, percentual: Decimal, minimo: Decimal) -> Decimal:
    valor = Decimal(str(valor or 0))
    if valor <= 0:
        return Decimal("0.00")
    percentual = Decimal(str(percentual or 0))
    minimo = Decimal(str(minimo or 0))
    calculada = (valor * percentual / Decimal("100")).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
    return max(calculada, minimo).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
