from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import APP_ENV, MERCADO_PAGO_API_BASE_URL, PUBLIC_API_BASE_URL, PUBLIC_CLIENT_BASE_URL
from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial
from app.models.lojamercadopago import LojaMercadoPago
from app.services.mercado_pago_oauth_service import expira_em, renovar_tokens


def _ambiente() -> str:
    # A chave da integração deve coincidir exatamente com a criada no OAuth.
    # Não normalizamos "prod" para evitar procurar outra conexão no banco.
    return APP_ENV


async def obter_token_loja(db: Session, loja_id: int) -> tuple[str, LojaMercadoPago]:
    config = db.query(LojaMercadoPago).filter(
        LojaMercadoPago.loja_id == loja_id,
        LojaMercadoPago.ambiente == _ambiente(),
        LojaMercadoPago.statusintegracao == "ATIVA",
    ).first()
    if not config or not config.access_token_criptografado:
        raise HTTPException(409, "A conta Mercado Pago do estabelecimento ainda não está conectada.")

    if config.token_expira_em and config.token_expira_em <= datetime.now():
        if not config.refresh_token_criptografado:
            config.statusintegracao = "EXPIRADA"
            db.commit()
            raise HTTPException(409, "A autorização Mercado Pago expirou. Conecte a conta novamente.")
        tokens = await renovar_tokens(
            refresh_token=descriptografar_credencial(config.refresh_token_criptografado)
        )
        config.access_token_criptografado = criptografar_credencial(str(tokens["access_token"]))
        novo_refresh = str(tokens.get("refresh_token") or "")
        if novo_refresh:
            config.refresh_token_criptografado = criptografar_credencial(novo_refresh)
        config.token_expira_em = expira_em(tokens)
        config.statusintegracao = "ATIVA"
        db.commit()
    return descriptografar_credencial(config.access_token_criptografado), config


def _url_retorno(acao: str, external_reference: str) -> str | None:
    if not PUBLIC_CLIENT_BASE_URL:
        return None
    # O Client Web é uma SPA. Mantemos o retorno na raiz e levamos uma
    # referência não sensível do checkout para que ele consulte a API após o
    # redirecionamento. Sem isso, o navegador voltava para o app sem saber
    # qual preferência Mercado Pago deveria confirmar.
    parametros = urlencode(
        {
            "pagamento": "mercado_pago",
            "acao": acao,
            "referencia": external_reference,
        }
    )
    return f"{PUBLIC_CLIENT_BASE_URL}/?{parametros}"


async def criar_preferencia(
    *,
    access_token: str,
    external_reference: str,
    titulo: str,
    itens: list[dict[str, Any]],
    valor_taxa_clubbar: Decimal,
    metodo: str,
) -> dict[str, Any]:
    payment_methods: dict[str, Any] = {}
    if metodo == "PIX":
        # Checkout Pro mantém somente PIX para o botão específico do Client.
        payment_methods["excluded_payment_types"] = [
            {"id": "credit_card"}, {"id": "debit_card"}, {"id": "ticket"},
        ]
    elif metodo in {"CREDIT_CARD", "CREDITO"}:
        payment_methods["excluded_payment_methods"] = [{"id": "pix"}]

    dados: dict[str, Any] = {
        "items": itens,
        "external_reference": external_reference,
        "statement_descriptor": "CLUBBAR",
        "metadata": {"origem": "CLUBBAR", "tipo": titulo},
        "payment_methods": payment_methods,
    }
    if valor_taxa_clubbar > 0:
        # No Split 1:1 é a comissão fixa que vai para o marketplace Clubbar.
        dados["marketplace_fee"] = float(valor_taxa_clubbar)
    if PUBLIC_API_BASE_URL:
        dados["notification_url"] = f"{PUBLIC_API_BASE_URL}/mercado-pago/webhook"
    back_urls = {
        chave: url
        for chave, url in {
            "success": _url_retorno("sucesso", external_reference),
            "pending": _url_retorno("pendente", external_reference),
            "failure": _url_retorno("cancelado", external_reference),
        }.items()
        if url
    }
    if back_urls:
        dados["back_urls"] = back_urls
        dados["auto_return"] = "approved"

    async with httpx.AsyncClient(timeout=25) as cliente:
        resposta = await cliente.post(
            f"{MERCADO_PAGO_API_BASE_URL}/checkout/preferences",
            headers={"Authorization": f"Bearer {access_token}"},
            json=dados,
        )
    if resposta.is_error:
        raise HTTPException(502, "Não foi possível criar o checkout Mercado Pago.")
    retorno = resposta.json()
    if not retorno.get("id") or not (retorno.get("init_point") or retorno.get("sandbox_init_point")):
        raise HTTPException(502, "Mercado Pago não retornou o link de pagamento.")
    return retorno


async def buscar_pagamento_por_referencia(*, access_token: str, external_reference: str) -> dict | None:
    async with httpx.AsyncClient(timeout=20) as cliente:
        resposta = await cliente.get(
            f"{MERCADO_PAGO_API_BASE_URL}/v1/payments/search",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"external_reference": external_reference, "sort": "date_created", "criteria": "desc"},
        )
    if resposta.is_error:
        raise HTTPException(502, "Não foi possível consultar o pagamento no Mercado Pago.")
    for pagamento in resposta.json().get("results") or []:
        if str(pagamento.get("status") or "").lower() == "approved":
            return pagamento
    return None


async def buscar_pagamento_por_id(*, access_token: str, payment_id: str) -> dict | None:
    async with httpx.AsyncClient(timeout=20) as cliente:
        resposta = await cliente.get(
            f"{MERCADO_PAGO_API_BASE_URL}/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resposta.status_code == 404:
        return None
    if resposta.is_error:
        raise HTTPException(502, "Não foi possível consultar a notificação Mercado Pago.")
    return resposta.json()
