from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import APP_ENV, ASAAS_CLUBBAR_WALLET_ID
from app.core.credential_crypto import descriptografar_credencial
from app.models.campanha_doacao import CampanhaDoacao
from app.models.lojaasaas import LojaAsaas


def _ambiente_asaas() -> str:
    return "production" if APP_ENV in {"production", "prod"} else "sandbox"


def obter_conta_asaas_da_loja(db: Session, loja_id: int) -> tuple[str, str]:
    config = (
        db.query(LojaAsaas)
        .filter(
            LojaAsaas.loja_id == loja_id,
            LojaAsaas.ambiente == _ambiente_asaas(),
        )
        .first()
    )
    if not config or not config.asaas_api_key_criptografada:
        raise HTTPException(
            status_code=422,
            detail="Ative os recebimentos Asaas deste estabelecimento antes de vender.",
        )
    if (config.statusintegracao or "").upper() != "ATIVA":
        raise HTTPException(
            status_code=422,
            detail="A subconta Asaas do estabelecimento ainda não está aprovada.",
        )
    if not ASAAS_CLUBBAR_WALLET_ID:
        raise HTTPException(
            status_code=503,
            detail="ASAAS_CLUBBAR_WALLET_ID não configurado no ambiente da API.",
        )
    if config.asaas_wallet_id == ASAAS_CLUBBAR_WALLET_ID:
        raise HTTPException(
            status_code=503,
            detail="A carteira Clubbar não pode ser a mesma carteira da subconta da loja.",
        )
    return (
        descriptografar_credencial(config.asaas_api_key_criptografada),
        config.asaas_wallet_id,
    )


def montar_split_clubbar(valor_taxa: Decimal | float, *, parcelado: bool = False) -> list[dict]:
    taxa = Decimal(str(valor_taxa or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if taxa <= 0:
        return []
    campo = "totalFixedValue" if parcelado else "fixedValue"
    return [{
        "walletId": ASAAS_CLUBBAR_WALLET_ID,
        campo: float(taxa),
        "externalReference": "TAXA-CLUBBAR",
        "description": "Taxa de serviço Clubbar",
    }]


def montar_splits_pagamento(
    valor_taxa: Decimal | float,
    *,
    campanha_doacao: CampanhaDoacao | None = None,
    parcelado: bool = False,
    para_checkout: bool = False,
) -> list[dict]:
    """Monta a taxa Clubbar e, quando ativa, a doação do parceiro.

    O percentual da doação é calculado pelo Asaas sobre o valor líquido. A
    taxa Clubbar permanece fixa, exatamente como já ocorre hoje.
    """
    splits = montar_split_clubbar(valor_taxa, parcelado=parcelado)
    if not campanha_doacao:
        return splits

    # A API de Checkout usa percentageValue; a criação direta de cobrança usa
    # percentualValue. Cada endpoint rejeita a outra grafia.
    campo_percentual = "percentageValue" if para_checkout else "percentualValue"
    splits.append({
        "walletId": campanha_doacao.asaas_wallet_id,
        campo_percentual: float(campanha_doacao.percentual_doacao),
        "externalReference": f"DOACAO-{campanha_doacao.campanhadoacao_id}",
        "description": f"Doação: {campanha_doacao.nmcampanha}"[:500],
    })
    return splits
