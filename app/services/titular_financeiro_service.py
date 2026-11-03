import secrets

from sqlalchemy.orm import Session

import os

from fastapi import HTTPException
from app.core.credential_crypto import hash_token_webhook
from app.models.loja import Loja
from app.models.lojaasaas import LojaAsaas
from app.models.titularfinanceiro import TitularFinanceiro


def ambiente_asaas() -> str:
    url = os.getenv("ASAAS_BASE_URL", "https://api-sandbox.asaas.com/v3").lower()
    return "sandbox" if "api-sandbox.asaas.com" in url else "production"


def sincronizar_integracao_asaas_da_loja(
    db: Session,
    loja: Loja,
    titular: TitularFinanceiro,
) -> None:
    """Faz a loja usar a subconta Asaas do titular financeiro selecionado."""
    ambiente = ambiente_asaas()
    if ambiente == "production" and titular.asaas_account_id:
        conta_teste = db.query(LojaAsaas).filter(
            LojaAsaas.ambiente == "sandbox",
            LojaAsaas.asaas_account_id == titular.asaas_account_id,
        ).first()
        if conta_teste:
            raise HTTPException(409, "Este titular está vinculado a uma subconta Asaas de teste. Vincule uma conta de produção antes de receber vendas reais.")
    configuracao = (
        db.query(LojaAsaas)
        .filter(
            LojaAsaas.loja_id == loja.loja_id,
            LojaAsaas.ambiente == ambiente,
        )
        .first()
    )

    credenciais_completas = all(
        (
            titular.asaas_account_id,
            titular.asaas_wallet_id,
            titular.asaas_api_key_criptografada,
        )
    )
    if not credenciais_completas:
        if configuracao is not None:
            db.delete(configuracao)
        return

    if configuracao is None:
        configuracao = LojaAsaas(
            organizacao_id=loja.organizacao_id,
            loja_id=loja.loja_id,
            ambiente=ambiente,
            webhook_token_hash=hash_token_webhook(secrets.token_urlsafe(32)),
            asaas_wallet_id=titular.asaas_wallet_id,
            asaas_api_key_criptografada=titular.asaas_api_key_criptografada,
        )
        db.add(configuracao)

    configuracao.organizacao_id = loja.organizacao_id
    configuracao.asaas_account_id = titular.asaas_account_id
    configuracao.asaas_wallet_id = titular.asaas_wallet_id
    configuracao.asaas_api_key_criptografada = (
        titular.asaas_api_key_criptografada
    )
    configuracao.statusintegracao = (
        "ATIVA" if titular.status_asaas == "APROVADO" else "PENDENTE"
    )

