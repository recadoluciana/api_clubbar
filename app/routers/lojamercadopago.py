from __future__ import annotations

import secrets
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from sqlalchemy import case
import httpx

from app.core.config import APP_ENV, PUBLIC_PARTNER_BASE_URL
from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial, hash_token_webhook
from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.loja import Loja
from app.models.checkout_mercadopago import CheckoutMercadoPago
from app.models.lojamercadopago import LojaMercadoPago, LojaMercadoPagoPendente
from app.schemas.lojamercadopago import (
    LojaMercadoPagoOut,
    MercadoPagoConfirmacaoIn,
    MercadoPagoAutorizacaoOut,
    ProvedorPagamentoIn,
)
from app.services.mercado_pago_oauth_service import (
    expira_em,
    montar_url_autorizacao,
    trocar_codigo_por_tokens,
    obter_nome_usuario,
    obter_dados_titular,
)
from app.services.mercado_pago_service import obter_token_loja


router = APIRouter(tags=["Integração Mercado Pago das lojas"])
logger = logging.getLogger(__name__)


def _loja_autorizada(db: Session, loja_id: int, usuario: dict) -> Loja:
    if usuario.get("role") != "usuario":
        raise HTTPException(status_code=403, detail="Acesso não autorizado")
    try:
        organizacao_id = int(usuario.get("organizacao_id"))
    except (TypeError, ValueError) as erro:
        raise HTTPException(status_code=403, detail="Token sem organização válida") from erro
    loja = db.query(Loja).filter(
        Loja.loja_id == loja_id,
        Loja.organizacao_id == organizacao_id,
    ).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada na organização")
    validar_mutacao_loja(usuario, loja.organizacao_id, loja.loja_id)
    return loja


def _config(db: Session, loja_id: int) -> LojaMercadoPago | None:
    return db.query(LojaMercadoPago).filter(
        LojaMercadoPago.loja_id == loja_id,
        LojaMercadoPago.ambiente == APP_ENV,
    ).order_by(case((LojaMercadoPago.statusintegracao == "ATIVA", 0), else_=1), LojaMercadoPago.lojamercadopago_id.desc()).first()


def _saida(loja: Loja, config: LojaMercadoPago | None) -> dict:
    conectada = bool(
        config
        and config.statusintegracao == "ATIVA"
        and config.access_token_criptografado
        and config.mercadopago_user_id
    )
    return {
        "loja_id": int(loja.loja_id),
        "organizacao_id": int(loja.organizacao_id),
        "ambiente": APP_ENV,
        "mercadopago_user_id": config.mercadopago_user_id if config else None,
        "mercadopago_nome": config.mercadopago_nome if config else None,
        "statusintegracao": config.statusintegracao if config else "NAO_CONFIGURADA",
        "conectada": conectada,
        "provedor_pagamento": str(loja.provedor_pagamento or "ASAAS").upper(),
    }


@router.get("/lojas/{loja_id}/mercado-pago", response_model=LojaMercadoPagoOut)
async def consultar_mercado_pago(
    loja_id: int,
    incluir_dados_titular: bool = False,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja = _loja_autorizada(db, loja_id, usuario)
    config = _config(db, loja_id)
    saida = _saida(loja, config)
    if incluir_dados_titular and saida['conectada']:
        try:
            token, _ = await obter_token_loja(db, loja_id, lojamercadopago_id=config.lojamercadopago_id)
            titular = await obter_dados_titular(access_token=token, user_id=str(config.mercadopago_user_id))
            saida['mercadopago_titular'] = titular['nome']
            saida['mercadopago_email'] = titular['email']
        except (HTTPException, httpx.HTTPError, ValueError):
            logger.warning('Não foi possível consultar os dados do titular Mercado Pago para a loja %s', loja_id)
    pendente = _pendente(db, loja_id)
    if pendente and pendente.expira_em > datetime.now():
        dados = json.loads(descriptografar_credencial(pendente.credenciais))
        saida["conta_pendente"] = {
            "confirmacao_id": pendente.confirmacao_id,
            "nome": dados["nome"] or "Nome indisponivel",
            "user_id": str(dados["user_id"]),
        }
    return saida


@router.post(
    "/lojas/{loja_id}/mercado-pago/autorizacao",
    response_model=MercadoPagoAutorizacaoOut,
)
def iniciar_autorizacao_mercado_pago(
    loja_id: int,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja = _loja_autorizada(db, loja_id, usuario)
    config = _config(db, loja_id)
    if not config:
        config = LojaMercadoPago(
            loja_id=loja.loja_id,
            organizacao_id=loja.organizacao_id,
            ambiente=APP_ENV,
            statusintegracao="PENDENTE",
        )
        db.add(config)
    state = secrets.token_urlsafe(32)
    config.oauth_state_hash = hash_token_webhook(state)
    config.oauth_state_expira_em = datetime.now() + timedelta(minutes=10)
    pendente = _pendente(db, loja_id)
    if pendente:
        db.delete(pendente)
    db.commit()
    return {"authorization_url": montar_url_autorizacao(state=state)}


@router.get("/mercado-pago/oauth/callback", include_in_schema=False)
async def concluir_autorizacao_mercado_pago(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    destino = PUBLIC_PARTNER_BASE_URL or "/"
    parametros: dict[str, str] = {"integracao": "mercado-pago"}
    if error or not code or not state:
        parametros["status"] = "cancelada"
        return RedirectResponse(f"{destino}?{urlencode(parametros)}")

    config = db.query(LojaMercadoPago).filter(
        LojaMercadoPago.ambiente == APP_ENV,
        LojaMercadoPago.oauth_state_hash == hash_token_webhook(state),
        LojaMercadoPago.oauth_state_expira_em >= datetime.now(),
    ).first()
    if not config:
        parametros["status"] = "erro_estado"
        return RedirectResponse(f"{destino}?{urlencode(parametros)}")

    try:
        tokens = await trocar_codigo_por_tokens(code=code)
        tokens["nome"] = await obter_nome_usuario(
            access_token=str(tokens["access_token"]), user_id=str(tokens["user_id"])
        )
        validade = expira_em(tokens)
        tokens["validade"] = validade.isoformat() if validade else None
        pendente = _pendente(db, config.loja_id)
        if pendente:
            db.delete(pendente)
            db.flush()
        db.add(LojaMercadoPagoPendente(
            loja_id=config.loja_id, ambiente=APP_ENV,
            confirmacao_id=secrets.token_urlsafe(32),
            credenciais=criptografar_credencial(json.dumps(tokens)),
            expira_em=datetime.now() + timedelta(minutes=10),
        ))
        config.oauth_state_hash = None
        config.oauth_state_expira_em = None
        db.commit()
        return HTMLResponse("""<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<title>Confirmar conta Mercado Pago</title><body>
<p>Volte a tela de Recebimentos do Clubbar Partner para confirmar a conta autorizada.</p>
<script>window.close();</script></body></html>""")
    except HTTPException:
        db.rollback()
        parametros["status"] = "erro_autorizacao"
    return RedirectResponse(f"{destino}?{urlencode(parametros)}")


def _pendente(db, loja_id):
    return db.query(LojaMercadoPagoPendente).filter_by(loja_id=loja_id, ambiente=APP_ENV).first()


@router.post("/lojas/{loja_id}/mercado-pago/confirmacao", response_model=LojaMercadoPagoOut)
def confirmar_conta_mercado_pago(
    loja_id: int, payload: MercadoPagoConfirmacaoIn,
    usuario: dict = Depends(get_usuario_logado), db: Session = Depends(get_db),
):
    loja = _loja_autorizada(db, loja_id, usuario)
    pendente = db.query(LojaMercadoPagoPendente).filter_by(
        loja_id=loja_id, ambiente=APP_ENV
    ).with_for_update().first()
    if not pendente or not secrets.compare_digest(pendente.confirmacao_id, payload.confirmacao_id):
        raise HTTPException(409, "Autorizacao indisponivel. Conecte novamente.")
    if pendente.expira_em <= datetime.now():
        raise HTTPException(409, "Autorizacao expirada. Conecte novamente.")
    config = _config(db, loja_id)
    if not config:
        raise HTTPException(409, "Conecte novamente a conta Mercado Pago.")
    if payload.confirmar:
        dados = json.loads(descriptografar_credencial(pendente.credenciais))
        # As credenciais de contas antigas continuam vinculadas às vendas.
        db.query(Loja).filter(Loja.loja_id == loja_id).with_for_update().first()
        atual = config
        existente = db.query(LojaMercadoPago).filter_by(
            loja_id=loja_id, ambiente=APP_ENV,
            mercadopago_user_id=str(dados["user_id"]),
        ).first()
        if existente:
            config = existente
        elif config.mercadopago_user_id:
            config = LojaMercadoPago(loja_id=loja_id, organizacao_id=loja.organizacao_id, ambiente=APP_ENV)
            db.add(config)
        if atual is not config and atual.statusintegracao == "ATIVA":
            atual.statusintegracao = "INATIVA"
        config.mercadopago_user_id = str(dados["user_id"])
        config.mercadopago_nome = dados["nome"]
        config.public_key = dados.get("public_key")
        config.access_token_criptografado = criptografar_credencial(dados["access_token"])
        config.refresh_token_criptografado = (
            criptografar_credencial(dados["refresh_token"]) if dados.get("refresh_token") else None
        )
        config.token_expira_em = datetime.fromisoformat(dados["validade"]) if dados.get("validade") else None
        config.statusintegracao = "ATIVA"
    db.delete(pendente)
    db.commit()
    return _saida(loja, config)


@router.post("/lojas/{loja_id}/mercado-pago/desconectar", response_model=LojaMercadoPagoOut)
def desconectar_mercado_pago(
    loja_id: int, usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja = _loja_autorizada(db, loja_id, usuario)
    config = _config(db, loja_id)
    pendente = db.query(CheckoutMercadoPago).filter(
        CheckoutMercadoPago.loja_id == loja_id,
        CheckoutMercadoPago.venda_id.is_(None),
        CheckoutMercadoPago.status.notin_(["CANCELLED", "CANCELED", "EXPIRED", "REJECTED", "REFUNDED"]),
    ).first()
    if pendente:
        raise HTTPException(409, "Existem pagamentos pendentes nesta loja. Aguarde a conclusão ou o cancelamento antes de desconectar.")
    autorizacao = _pendente(db, loja_id)
    if autorizacao:
        db.delete(autorizacao)
    if config:
        config.statusintegracao = "INATIVA"
        config.oauth_state_hash = None
        config.oauth_state_expira_em = None
    db.commit()
    return _saida(loja, config)


@router.put("/lojas/{loja_id}/provedor-pagamento", response_model=LojaMercadoPagoOut)
def selecionar_provedor_pagamento(
    loja_id: int,
    payload: ProvedorPagamentoIn,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja = _loja_autorizada(db, loja_id, usuario)
    config = _config(db, loja_id)
    if payload.provedor_pagamento == "MERCADO_PAGO":
        if not config or config.statusintegracao != "ATIVA" or not config.access_token_criptografado:
            raise HTTPException(
                status_code=409,
                detail="Conecte uma conta Mercado Pago ativa antes de selecioná-la.",
            )
    loja.provedor_pagamento = payload.provedor_pagamento
    db.commit()
    db.refresh(loja)
    return _saida(loja, config)
