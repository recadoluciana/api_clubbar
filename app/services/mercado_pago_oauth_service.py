from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from app.core.config import (
    MERCADO_PAGO_API_BASE_URL,
    MERCADO_PAGO_CLIENT_ID,
    MERCADO_PAGO_CLIENT_SECRET,
    MERCADO_PAGO_OAUTH_REDIRECT_URL,
)


def validar_configuracao_marketplace() -> None:
    ausentes = [
        nome
        for nome, valor in {
            "MERCADO_PAGO_CLIENT_ID": MERCADO_PAGO_CLIENT_ID,
            "MERCADO_PAGO_CLIENT_SECRET": MERCADO_PAGO_CLIENT_SECRET,
            "MERCADO_PAGO_OAUTH_REDIRECT_URL": MERCADO_PAGO_OAUTH_REDIRECT_URL,
        }.items()
        if not valor
    ]
    if ausentes:
        raise HTTPException(
            status_code=503,
            detail=f"Integração Mercado Pago não configurada: {', '.join(ausentes)}",
        )


def montar_url_autorizacao(*, state: str) -> str:
    validar_configuracao_marketplace()
    parametros = urlencode(
        {
            "client_id": MERCADO_PAGO_CLIENT_ID,
            "response_type": "code",
            "platform_id": "mp",
            "redirect_uri": MERCADO_PAGO_OAUTH_REDIRECT_URL,
            "state": state,
        }
    )
    return f"https://auth.mercadopago.com.br/authorization?{parametros}"


async def trocar_codigo_por_tokens(*, code: str) -> dict:
    validar_configuracao_marketplace()
    dados = {
        "client_id": MERCADO_PAGO_CLIENT_ID,
        "client_secret": MERCADO_PAGO_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": MERCADO_PAGO_OAUTH_REDIRECT_URL,
    }
    async with httpx.AsyncClient(timeout=20) as cliente:
        resposta = await cliente.post(f"{MERCADO_PAGO_API_BASE_URL}/oauth/token", data=dados)
    if resposta.is_error:
        raise HTTPException(502, "Mercado Pago recusou a autorização da conta.")
    retorno = resposta.json()
    if not retorno.get("access_token") or not retorno.get("user_id"):
        raise HTTPException(502, "Mercado Pago não retornou os dados da conta autorizada.")
    return retorno


async def renovar_tokens(*, refresh_token: str) -> dict:
    validar_configuracao_marketplace()
    dados = {
        "client_id": MERCADO_PAGO_CLIENT_ID,
        "client_secret": MERCADO_PAGO_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    async with httpx.AsyncClient(timeout=20) as cliente:
        resposta = await cliente.post(f"{MERCADO_PAGO_API_BASE_URL}/oauth/token", data=dados)
    if resposta.is_error:
        raise HTTPException(502, "Não foi possível renovar a autorização Mercado Pago da loja.")
    retorno = resposta.json()
    if not retorno.get("access_token"):
        raise HTTPException(502, "Mercado Pago não retornou um novo token de acesso.")
    return retorno


async def obter_nome_usuario(*, access_token: str, user_id: str) -> str | None:
    """Obtém um nome seguro para identificar a conta autorizada no Partner."""
    async with httpx.AsyncClient(timeout=20) as cliente:
        resposta = await cliente.get(
            f"{MERCADO_PAGO_API_BASE_URL}/users/{user_id}",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resposta.is_error:
        return None
    dados = resposta.json()
    nome = str(dados.get("nickname") or "").strip()
    if nome:
        return nome
    partes = [str(dados.get(chave) or "").strip() for chave in ("first_name", "last_name")]
    nome = " ".join(parte for parte in partes if parte)
    return nome or None


def expira_em(tokens: dict) -> datetime:
    # Renovamos com margem para não iniciar um checkout com credencial vencendo.
    segundos = int(tokens.get("expires_in") or 0)
    return datetime.now() + timedelta(seconds=max(0, segundos - 300))
