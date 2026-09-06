import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import ASAAS_API_KEY, PUBLIC_SITE_URL
from app.models.cobrancaimplantacao import CobrancaImplantacao
from app.models.contratolead import LeadEstabelecimentoContrato
from app.services.asaas_service import ASAAS_BASE_URL, buscar_pagamento_confirmado_por_checkout


def saida_cobranca(item: CobrancaImplantacao | None) -> dict | None:
    if not item:
        return None
    return {
        "cobrancaimplantacao_id": item.cobrancaimplantacao_id,
        "leadestabelecimentocontrato_id": item.leadestabelecimentocontrato_id,
        "leadestabelecimento_id": item.leadestabelecimento_id,
        "organizacao_id": item.organizacao_id,
        "valor": float(item.valor),
        "status": item.status,
        "checkout_url": item.asaas_checkout_url,
        "billing_type": item.billing_type,
        "dtvencimento": item.dtvencimento,
        "dtpagamento": item.dtpagamento,
        "dtisencao": item.dtisencao,
        "justificativaisencao": item.justificativaisencao,
    }


async def criar_cobranca_implantacao(
    db: Session, contrato: LeadEstabelecimentoContrato,
) -> CobrancaImplantacao:
    existente = db.query(CobrancaImplantacao).filter(
        CobrancaImplantacao.leadestabelecimentocontrato_id
        == contrato.leadestabelecimentocontrato_id
    ).first()
    if existente and existente.status in {"PAGA", "ISENTA"}:
        return existente
    if existente and existente.status == "PENDENTE" and existente.asaas_checkout_url:
        return existente
    if not ASAAS_API_KEY:
        raise HTTPException(503, "Conta Asaas do Clubbar não configurada")
    if not PUBLIC_SITE_URL:
        raise HTTPException(503, "PUBLIC_SITE_URL não configurada")

    referencia = f"IMPLANTACAO-{contrato.leadestabelecimentocontrato_id}-{uuid.uuid4().hex[:12]}"
    retorno = f"{PUBLIC_SITE_URL}/portal-lead.html"
    body = {
        "billingTypes": ["PIX", "CREDIT_CARD"],
        "chargeTypes": ["DETACHED"],
        "minutesToExpire": 1440,
        "externalReference": referencia,
        "callback": {"successUrl": retorno, "cancelUrl": retorno, "expiredUrl": retorno},
        "items": [{
            "externalReference": referencia,
            "name": "Implantacao Clubbar",
            "description": "Ativacao, configuracao inicial, treinamento e acompanhamento da primeira venda",
            "quantity": 1,
            "value": round(float(contrato.vrimplantacao), 2),
        }],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{ASAAS_BASE_URL.rstrip('/')}/checkouts",
            headers={"accept": "application/json", "content-type": "application/json", "access_token": ASAAS_API_KEY},
            json=body,
        )
    try:
        data = response.json()
    except Exception:
        data = {"raw": response.text}
    if response.status_code >= 400:
        raise HTTPException(response.status_code, data)
    if not data.get("id") or not data.get("link"):
        raise HTTPException(502, "Asaas não retornou o checkout da implantação")
    if not existente:
        existente = CobrancaImplantacao(
            leadestabelecimentocontrato_id=contrato.leadestabelecimentocontrato_id,
            leadestabelecimento_id=contrato.leadestabelecimento_id,
            valor=contrato.vrimplantacao,
            external_reference=referencia,
        )
        db.add(existente)
    existente.valor = contrato.vrimplantacao
    existente.status = "PENDENTE"
    existente.asaas_checkout_id = str(data["id"])
    existente.asaas_checkout_url = str(data["link"])
    existente.external_reference = referencia
    existente.dtvencimento = datetime.now() + timedelta(days=1)
    db.commit()
    db.refresh(existente)
    return existente


async def reconciliar_cobranca_implantacao(
    db: Session, cobranca: CobrancaImplantacao,
) -> CobrancaImplantacao:
    if cobranca.status in {"PAGA", "ISENTA", "CANCELADA"}:
        return cobranca
    if cobranca.dtvencimento and cobranca.dtvencimento <= datetime.now():
        cobranca.status = "VENCIDA"
        db.commit()
        return cobranca
    pagamento = await buscar_pagamento_confirmado_por_checkout(
        cobranca.asaas_checkout_id, ASAAS_API_KEY
    ) if cobranca.asaas_checkout_id else None
    if not pagamento:
        return cobranca
    referencia = str(pagamento.get("externalReference") or "")
    valor = Decimal(str(pagamento.get("value") or 0)).quantize(Decimal("0.01"))
    esperado = Decimal(str(cobranca.valor)).quantize(Decimal("0.01"))
    if referencia != cobranca.external_reference or valor != esperado:
        raise HTTPException(409, "Cobrança de implantação divergente no Asaas")
    cobranca.status = "PAGA"
    cobranca.asaas_payment_id = str(pagamento.get("id") or "") or None
    cobranca.billing_type = pagamento.get("billingType")
    cobranca.dtpagamento = datetime.now()
    db.commit()
    db.refresh(cobranca)
    return cobranca
