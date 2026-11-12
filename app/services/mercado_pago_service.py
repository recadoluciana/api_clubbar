from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import (
    APP_ENV,
    MERCADO_PAGO_API_BASE_URL,
    MERCADO_PAGO_OAUTH_TEST_TOKEN,
    MERCADO_PAGO_TEST_PAYER_EMAIL,
    PUBLIC_API_BASE_URL,
    PUBLIC_CLIENT_BASE_URL,
)
from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial
from app.models.lojamercadopago import LojaMercadoPago
from app.models.loja import Loja
from app.models.checkout_mercadopago import CheckoutMercadoPago
from sqlalchemy import or_, exists
from app.services.mercado_pago_oauth_service import expira_em, renovar_tokens


logger = logging.getLogger(__name__)


def pix_em_sandbox() -> bool:
    return APP_ENV not in {"production", "prod"} and MERCADO_PAGO_OAUTH_TEST_TOKEN


def _email_pagador_pix(email_pagador: str) -> str:
    email = (email_pagador or "").strip().lower()
    if pix_em_sandbox():
        email = MERCADO_PAGO_TEST_PAYER_EMAIL or email
        if not re.fullmatch(r"test_user_[a-z0-9_]+@testuser\.com", email):
            raise HTTPException(
                409,
                "PIX de teste: configure MERCADO_PAGO_TEST_PAYER_EMAIL na API "
                "com o e-mail da conta Comprador de teste do Mercado Pago. "
                "O cadastro do cliente no Clubbar não precisa ser alterado.",
            )
    if not email:
        raise HTTPException(409, "O e-mail do cliente é obrigatório para gerar o PIX.")
    return email


def _ambiente() -> str:
    # A chave da integração deve coincidir exatamente com a criada no OAuth.
    # Não normalizamos "prod" para evitar procurar outra conexão no banco.
    return APP_ENV


async def obter_token_loja(db: Session, loja_id: int, lojamercadopago_id: int | None = None) -> tuple[str, LojaMercadoPago]:
    consulta = db.query(LojaMercadoPago).filter(LojaMercadoPago.ambiente == _ambiente())
    if lojamercadopago_id is None:
        loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
        if not loja or not loja.titularfinanceiro_id:
            raise HTTPException(409, "O estabelecimento não possui titular financeiro vinculado.")
        consulta = consulta.filter(LojaMercadoPago.titularfinanceiro_id == loja.titularfinanceiro_id, LojaMercadoPago.statusintegracao == "ATIVA")
    else:
        historico = exists().where(CheckoutMercadoPago.loja_id == loja_id, CheckoutMercadoPago.lojamercadopago_id == LojaMercadoPago.lojamercadopago_id)
        consulta = consulta.filter(LojaMercadoPago.lojamercadopago_id == lojamercadopago_id, or_(LojaMercadoPago.loja_id == loja_id, historico))
    config = consulta.first()
    if not config or not config.access_token_criptografado:
        raise HTTPException(409, "A conta Mercado Pago do estabelecimento ainda não está conectada.")

    if config.token_expira_em and config.token_expira_em <= datetime.now():
        config = db.query(LojaMercadoPago).filter(
            LojaMercadoPago.lojamercadopago_id == config.lojamercadopago_id
        ).populate_existing().with_for_update().first()
        if not config:
            raise HTTPException(409, 'A conta Mercado Pago não está mais disponível.')
        if not config.token_expira_em or config.token_expira_em > datetime.now():
            return descriptografar_credencial(config.access_token_criptografado), config
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


async def estornar_pagamento_mercado_pago(*, access_token: str, payment_id: str, venda_id: int) -> dict:
    """Solicita estorno integral usando sempre a conta que recebeu a venda."""
    chave = str(uuid.uuid5(uuid.NAMESPACE_URL, f"clubbar:estorno:{venda_id}:{payment_id}"))
    try:
        async with httpx.AsyncClient(timeout=25) as cliente:
            resposta = await cliente.post(
                f"{MERCADO_PAGO_API_BASE_URL}/v1/payments/{payment_id}/refunds",
                headers={"Authorization": f"Bearer {access_token}", "X-Idempotency-Key": chave},
            )
    except httpx.RequestError as erro:
        raise HTTPException(502, "Não foi possível confirmar o estorno no Mercado Pago; procure o suporte.") from erro
    if resposta.status_code >= 500:
        raise HTTPException(502, "O Mercado Pago ainda não confirmou o estorno; procure o suporte.")
    if resposta.status_code >= 400:
        try:
            erro_mp = resposta.json()
        except ValueError:
            erro_mp = {}
        if not isinstance(erro_mp, dict):
            erro_mp = {}
        def codigo_seguro(valor: Any) -> str:
            valor = str(valor or "")[:80]
            return valor if re.fullmatch(r"[a-zA-Z0-9_.-]+", valor) else "indisponivel"
        def descricao_segura(valor: Any) -> str:
            valor = str(valor or "")[:160]
            return valor if re.fullmatch(r"[a-zA-Z0-9_ .,:'()/-]+", valor) else "indisponivel"
        mensagem = descricao_segura(erro_mp.get("message"))
        causas = erro_mp.get("cause") or []
        codigos = [codigo_seguro(c.get("code")) for c in causas if isinstance(c, dict)] if isinstance(causas, list) else []
        descricoes = [descricao_segura(c.get("description")) for c in causas if isinstance(c, dict)] if isinstance(causas, list) else []
        logger.warning(
            "Mercado Pago recusou estorno venda=%s pagamento=%s http=%s erro=%s mensagem=%s causas=%s descricoes=%s request_id=%s",
            venda_id, payment_id, resposta.status_code, codigo_seguro(erro_mp.get("error")),
            mensagem, codigos, descricoes, codigo_seguro(resposta.headers.get("x-request-id")),
        )
        if "2031" in codigos or "2030" in codigos:
            raise HTTPException(409, "O Mercado Pago informou saldo insuficiente para o estorno. O estabelecimento precisa verificar o saldo disponível.")
        raise HTTPException(409, "O Mercado Pago recusou o estorno. Procure o suporte para verificar o motivo.")
    try:
        resultado = resposta.json()
    except ValueError as erro:
        raise HTTPException(502, "Resposta de estorno inválida; procure o suporte.") from erro
    if str(resultado.get("status") or "").lower() != "approved":
        raise HTTPException(503, "O estorno ainda não foi confirmado pelo Mercado Pago; procure o suporte.")
    return resultado


def _valor_monetario(valor: Any) -> str:
    """Devolve valores no formato decimal exigido pela API Orders."""
    return format(Decimal(str(valor or 0)).quantize(Decimal("0.01")), ".2f")


async def criar_order_checkout_pro(
    *,
    access_token: str,
    external_reference: str,
    titulo: str,
    itens: list[dict[str, Any]],
    valor_total: Decimal,
    valor_taxa_clubbar: Decimal,
    email_pagador: str | None = None,
) -> dict[str, Any]:
    """Cria uma Order online do Checkout Pro para um Pix com split.

    A API de Orders é a versão atual do Checkout Pro. Ao configurar
    ``auto_return=approved`` ela redireciona automaticamente o navegador ao
    Clubbar depois da confirmação do Pix, sem exigir que o cliente toque em
    "Voltar para Clubbar" na página hospedada pelo Mercado Pago.
    """
    urls_retorno = {
        chave: url
        for chave, url in {
            "success_url": _url_retorno("sucesso", external_reference),
            "pending_url": _url_retorno("pendente", external_reference),
            "failure_url": _url_retorno("cancelado", external_reference),
        }.items()
        if url
    }
    if not urls_retorno.get("success_url"):
        raise HTTPException(
            500,
            "A URL pública do Clubbar não está configurada para receber o retorno do pagamento.",
        )

    itens_order: list[dict[str, Any]] = []
    for item in itens:
        quantidade = int(item.get("quantity") or 0)
        if quantidade <= 0:
            continue
        itens_order.append(
            {
                "title": str(item.get("title") or "Compra Clubbar")[:256],
                "quantity": quantidade,
                "unit_price": _valor_monetario(item.get("unit_price")),
            }
        )
    if not itens_order:
        raise HTTPException(422, "Não há itens válidos para criar o checkout Mercado Pago.")

    dados: dict[str, Any] = {
        "type": "online",
        "processing_mode": "manual",
        "capture_mode": "automatic_async",
        "external_reference": external_reference,
        "description": f"Clubbar - {titulo}"[:256],
        "total_amount": _valor_monetario(valor_total),
        "items": itens_order,
        "config": {
            "online": {
                **urls_retorno,
                "auto_return": "approved",
            }
        },
    }
    if (email_pagador or "").strip():
        dados["payer"] = {"email": email_pagador.strip().lower()}
    if valor_taxa_clubbar > 0:
        # É o valor em reais que pertence ao marketplace Clubbar no split.
        dados["marketplace_fee"] = _valor_monetario(valor_taxa_clubbar)

    try:
        async with httpx.AsyncClient(timeout=25) as cliente:
            resposta = await cliente.post(
                f"{MERCADO_PAGO_API_BASE_URL}/v1/orders",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "X-Idempotency-Key": str(uuid.uuid4()),
                    "Content-Type": "application/json",
                },
                json=dados,
            )
    except httpx.HTTPError as exc:
        logger.warning(
            "Falha de rede ao criar Order Mercado Pago: referencia=%s erro=%s",
            external_reference,
            type(exc).__name__,
        )
        raise HTTPException(
            502,
            "Não foi possível conectar ao Mercado Pago para criar o checkout. Tente novamente.",
        ) from exc
    if resposta.is_error:
        try:
            erro = resposta.json()
        except ValueError:
            erro = {}
        logger.warning(
            "Mercado Pago recusou Order: referencia=%s status=%s erro=%s mensagem=%s",
            external_reference,
            resposta.status_code,
            (erro or {}).get("error") if isinstance(erro, dict) else None,
            (erro or {}).get("message") if isinstance(erro, dict) else None,
        )
        raise HTTPException(422, "O Mercado Pago recusou criar este checkout. Tente novamente.")
    retorno = resposta.json()
    if not retorno.get("id") or not retorno.get("checkout_url"):
        raise HTTPException(502, "Mercado Pago não retornou o link de pagamento.")
    return retorno


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
        # O Checkout Pro identifica o PIX como método `pix` (tipo
        # `bank_transfer`). Definimos o PIX como opção inicial e removemos o
        # boleto; `credit_card` e `debit_card` não são tipos de exclusão
        # válidos para preferências do Checkout Pro.
        payment_methods["default_payment_method_id"] = "pix"
        payment_methods["excluded_payment_types"] = [
            {"id": "ticket"},
        ]
    elif metodo in {"CREDIT_CARD", "CREDITO"}:
        payment_methods["excluded_payment_methods"] = [{"id": "pix"}]
        payment_methods["excluded_payment_types"] = [
            {"id": tipo}
            for tipo in ("ticket", "bank_transfer", "debit_card", "account_money")
        ]

    dados: dict[str, Any] = {
        "items": itens,
        "external_reference": external_reference,
        "statement_descriptor": "CLUBBAR",
        "metadata": {"origem": "CLUBBAR", "tipo": titulo},
        "payment_methods": payment_methods,
        "expiration_date_from": datetime.now(
            ZoneInfo("America/Sao_Paulo")
        ).isoformat(timespec="milliseconds"),
        "expiration_date_to": (
            datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(minutes=5)
        ).isoformat(timespec="milliseconds"),
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
        try:
            detalhe = resposta.json()
        except ValueError:
            detalhe = {"body": resposta.text[:500]}
        logger.warning(
            "Mercado Pago recusou preferência: referencia=%s status=%s detalhe=%s",
            external_reference,
            resposta.status_code,
            detalhe,
        )
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


def descricao_venda_mercado_pago(nome_loja: str, instante: datetime | None = None) -> str:
    """Identifica o estabelecimento e o momento de criação do pagamento."""
    horario = instante or datetime.now(ZoneInfo("America/Sao_Paulo"))
    nome = " ".join((nome_loja or "Clubbar").split()) or "Clubbar"
    sufixo = horario.astimezone(ZoneInfo("America/Sao_Paulo")).strftime("%d/%m/%Y %H:%M")
    prefixo = "Venda - "
    return f"{prefixo}{nome[:256 - len(prefixo) - len(sufixo) - 3]} - {sufixo}"


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
    nome_loja: str | None = None,
) -> dict[str, Any]:
    """Cria Pix na conta OAuth do vendedor, com comissão do marketplace."""
    email = _email_pagador_pix(email_pagador)
    tipo_documento, numero_documento = _documento_pagador(documento_pagador)
    # O Mercado Pago exige ISO 8601 com milissegundos e offset com dois pontos,
    # por exemplo ``2026-10-27T00:30:00.000-03:00``. Além disso, PIX precisa
    # de ao menos 30 minutos de validade. Usar o fuso brasileiro também evita
    # enviar uma data ambígua em UTC para uma conta brasileira.
    expiracao = datetime.now(ZoneInfo("America/Sao_Paulo")) + timedelta(minutes=30)
    dados: dict[str, Any] = {
        "transaction_amount": float(valor),
        "description": descricao_venda_mercado_pago(nome_loja or "Clubbar"),
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
        dados["application_fee"] = float(valor_taxa_clubbar)
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
        if resposta.status_code >= 500:
            raise HTTPException(502, 'O Mercado Pago não confirmou a criação do PIX. Verifique o pagamento antes de tentar novamente.')
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
        if pix_em_sandbox() and isinstance(causas, list) and any(
            isinstance(causa, dict) and str(causa.get("code")) == "2034"
            for causa in causas
        ):
            raise HTTPException(
                409,
                "PIX de teste: o Mercado Pago recusou a combinação de contas. "
                "Confira a conta Vendedor conectada e MERCADO_PAGO_TEST_PAYER_EMAIL "
                "da conta Comprador de teste. Comprador, vendedor e marketplace "
                "devem ser contas de teste diferentes.",
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


async def criar_pagamento_cartao(
    *, access_token: str, external_reference: str, titulo: str,
    valor: Decimal, valor_taxa_clubbar: Decimal, card_token: str,
    payment_method_id: str, installments: int = 1, issuer_id: str | None = None,
    payer_email: str | None = None, payer_document: str | None = None,
    device_id: str | None = None, chave_idempotencia: str,
    nome_loja: str | None = None,
) -> dict[str, Any]:
    """Cria cartão tokenizado no checkout transparente do Mercado Pago."""
    if not card_token or not payment_method_id:
        raise HTTPException(422, "Token e método do cartão são obrigatórios.")
    dados: dict[str, Any] = {
        "transaction_amount": float(valor), "token": card_token,
        "description": descricao_venda_mercado_pago(nome_loja or "Clubbar"),
        "installments": max(1, int(installments or 1)),
        "payment_method_id": payment_method_id,
        "external_reference": external_reference,
        "payer": {"email": (payer_email or "").strip().lower()},
    }
    if issuer_id:
        dados["issuer_id"] = issuer_id
    if payer_document:
        numero = "".join(c for c in payer_document if c.isdigit())
        if numero:
            dados["payer"]["identification"] = {
                "type": "CPF" if len(numero) == 11 else "CNPJ", "number": numero,
            }
    if valor_taxa_clubbar > 0:
        dados["application_fee"] = float(valor_taxa_clubbar)
    if PUBLIC_API_BASE_URL:
        dados["notification_url"] = f"{PUBLIC_API_BASE_URL}/mercado-pago/webhook"
    headers = {"Authorization": f"Bearer {access_token}", "X-Idempotency-Key": chave_idempotencia, "Content-Type": "application/json"}
    if device_id:
        headers["X-meli-session-id"] = device_id
    async with httpx.AsyncClient(timeout=25) as cliente:
        resposta = await cliente.post(f"{MERCADO_PAGO_API_BASE_URL}/v1/payments", headers=headers, json=dados)
    if resposta.is_error:
        if resposta.status_code >= 500:
            raise HTTPException(502, 'O Mercado Pago não confirmou o pagamento. Verifique o status antes de tentar novamente.')
        raise HTTPException(422, "O Mercado Pago recusou o pagamento com cartão.")
    retorno = resposta.json()
    if not retorno.get("id"):
        raise HTTPException(502, "Mercado Pago não retornou o pagamento.")
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


async def cancelar_pagamento_por_id(*, access_token: str, payment_id: str) -> dict:
    """Cancela um pagamento ainda pendente no Mercado Pago."""
    async with httpx.AsyncClient(timeout=20) as cliente:
        resposta = await cliente.put(
            f"{MERCADO_PAGO_API_BASE_URL}/v1/payments/{payment_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"status": "cancelled"},
        )
    if resposta.is_error:
        raise HTTPException(502, "Não foi possível cancelar o pagamento no Mercado Pago.")
    return resposta.json()
