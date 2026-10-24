from __future__ import annotations

import secrets
from datetime import datetime, timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import APP_ENV, PUBLIC_PARTNER_BASE_URL
from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial, hash_token_webhook
from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.loja import Loja
from app.models.lojamercadopago import LojaMercadoPago
from app.schemas.lojamercadopago import (
    LojaMercadoPagoOut,
    MercadoPagoAutorizacaoOut,
    ProvedorPagamentoIn,
)
from app.services.mercado_pago_oauth_service import (
    expira_em,
    montar_url_autorizacao,
    trocar_codigo_por_tokens,
)


router = APIRouter(tags=["Integração Mercado Pago das lojas"])


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
    ).first()


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
        "statusintegracao": config.statusintegracao if config else "NAO_CONFIGURADA",
        "conectada": conectada,
        "provedor_pagamento": str(loja.provedor_pagamento or "ASAAS").upper(),
    }


@router.get("/lojas/{loja_id}/mercado-pago", response_model=LojaMercadoPagoOut)
def consultar_mercado_pago(
    loja_id: int,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja = _loja_autorizada(db, loja_id, usuario)
    return _saida(loja, _config(db, loja_id))


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
    config.statusintegracao = "PENDENTE"
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
        LojaMercadoPago.oauth_state_hash == hash_token_webhook(state),
        LojaMercadoPago.oauth_state_expira_em >= datetime.now(),
    ).first()
    if not config:
        parametros["status"] = "erro_estado"
        return RedirectResponse(f"{destino}?{urlencode(parametros)}")

    try:
        tokens = await trocar_codigo_por_tokens(code=code)
        config.mercadopago_user_id = str(tokens["user_id"])
        config.public_key = str(tokens.get("public_key") or "") or None
        config.access_token_criptografado = criptografar_credencial(str(tokens["access_token"]))
        refresh_token = str(tokens.get("refresh_token") or "")
        config.refresh_token_criptografado = (
            criptografar_credencial(refresh_token) if refresh_token else None
        )
        config.token_expira_em = expira_em(tokens)
        config.oauth_state_hash = None
        config.oauth_state_expira_em = None
        config.statusintegracao = "ATIVA"
        db.commit()
        parametros["status"] = "conectada"
    except HTTPException:
        db.rollback()
        parametros["status"] = "erro_autorizacao"
    return RedirectResponse(f"{destino}?{urlencode(parametros)}")


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
