from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import APP_ENV, MERCADO_PAGO_API_BASE_URL, PUBLIC_API_BASE_URL, PUBLIC_CLIENT_BASE_URL
from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial
from app.models.lojamercadopago import LojaMercadoPago
from app.services.mercado_pago_oauth_service import expira_em, renovar_tokens


logger = logging.getLogger(__name__)


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
    email_pagador: str | None = None,
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
    # Checkout Pro continua sendo uma página hospedada pelo Mercado Pago, mas
    # o e-mail válido do Clubbar evita que o cliente tenha de digitá-lo de
    # novo. Não enviamos CPF: o pagador pode usar cartão de outro titular.
    if (email_pagador or "").strip():
        dados["payer"] = {"email": email_pagador.strip().lower()}
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


def _documento_pagador(documento: str | None) -> tuple[str, str]:
    """Normaliza o documento exigido pelo Pix transparente do Mercado Pago."""
    numero = "".join(caractere for caractere in (documento or "") if caractere.isdigit())
    if len(numero) == 11:
        return "CPF", numero
    if len(numero) == 14:
        return "CNPJ", numero
    raise HTTPException(
        409,
        "Para gerar o PIX, complete o CPF ou CNPJ válido nos seus Dados pessoais.",
    )


async def criar_pagamento_pix(
    *,
    access_token: str,
    external_reference: str,
    titulo: str,
    valor: Decimal,
    valor_taxa_clubbar: Decimal,
    email_pagador: str,
    documento_pagador: str | None,
    chave_idempotencia: str,
) -> dict[str, Any]:
    """Cria um PIX transparente sem comissão de marketplace.

    Quando há comissão Clubbar, o chamador usa Checkout Pro com
    ``marketplace_fee``. A integração atual do Mercado Pago recusa
    ``application_fee`` neste endpoint para PIX (erro 2059).
    """
    email = (email_pagador or "").strip().lower()
    if not email:
        raise HTTPException(409, "O e-mail do cliente é obrigatório para gerar o PIX.")
    tipo_documento, numero_documento = _documento_pagador(documento_pagador)
    # O Mercado Pago exige ISO 8601 com milissegundos e offset com dois pontos,
    # por exemplo ``2026-10-27T00:30:00.000-03:00``. Além disso, PIX precisa
    # de ao menos 30 minutos de validade. Usar o fuso brasileiro também evita
    # enviar uma data ambígua em UTC para uma conta brasileira.
    expiracao = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(minutes=30)
    dados: dict[str, Any] = {
        "transaction_amount": float(valor),
        "description": f"Clubbar - {titulo}"[:256],
        "payment_method_id": "pix",
        "external_reference": external_reference,
        "date_of_expiration": expiracao.isoformat(timespec="milliseconds"),
        "metadata": {"origem": "CLUBBAR", "tipo": titulo},
        "payer": {
            "email": email,
            "identification": {"type": tipo_documento, "number": numero_documento},
        },
    }
    if valor_taxa_clubbar > 0:
        raise ValueError(
            "PIX transparente não suporta comissão Clubbar; use Checkout Pro."
        )
    if PUBLIC_API_BASE_URL:
        dados["notification_url"] = f"{PUBLIC_API_BASE_URL}/mercado-pago/webhook"

    try:
        async with httpx.AsyncClient(timeout=25) as cliente:
            resposta = await cliente.post(
                f"{MERCADO_PAGO_API_BASE_URL}/v1/payments",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Idempotency-Key": chave_idempotencia,
                    "Content-Type": "application/json",
                },
                json=dados,
            )
    except httpx.HTTPError as exc:
        logger.warning(
            "Falha de rede ao gerar PIX Mercado Pago: referencia=%s erro=%s",
            external_reference,
            type(exc).__name__,
        )
        raise HTTPException(
            502,
            "Não foi possível conectar ao Mercado Pago para gerar o PIX. Tente novamente.",
        ) from exc
    if resposta.is_error:
        # O detalhe do Mercado Pago é registrado no servidor sem tokens ou
        # dados pessoais. Isso permite corrigir configurações de split ou da
        # conta recebedora sem expor a resposta do provedor ao Client.
        try:
            erro = resposta.json()
        except ValueError:
            erro = {}
        causas = erro.get("cause") if isinstance(erro, dict) else None
        logger.warning(
            "Mercado Pago recusou PIX: referencia=%s status=%s erro=%s mensagem=%s causas=%s",
            external_reference,
            resposta.status_code,
            (erro or {}).get("error") if isinstance(erro, dict) else None,
            (erro or {}).get("message") if isinstance(erro, dict) else None,
            causas,
        )
        raise HTTPException(
            422,
            "O Mercado Pago recusou gerar este PIX. Verifique a conta recebedora e tente novamente.",
        )
    retorno = resposta.json()
    dados_pix = ((retorno.get("point_of_interaction") or {}).get("transaction_data") or {})
    if not retorno.get("id") or not dados_pix.get("qr_code"):
        raise HTTPException(502, "Mercado Pago não retornou o QR Code PIX.")
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
