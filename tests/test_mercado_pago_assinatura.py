import hashlib
import hmac
import asyncio
import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.routers import mercado_pago_webhook as webhook


def _request(query, manifest, secret, request_id=None):
    signature = hmac.new(secret.encode(), manifest.encode(), hashlib.sha256).hexdigest()
    headers = [(b'x-signature', f'ts=123,v1={signature}'.encode())]
    if request_id is not None:
        headers.append((b'x-request-id', request_id.encode()))
    return Request({'type': 'http', 'method': 'POST', 'path': '/mercado-pago/webhook',
                    'query_string': query.encode(), 'headers': headers})


def test_assinatura_usa_data_id_da_url(monkeypatch):
    monkeypatch.setattr(webhook, 'MERCADO_PAGO_WEBHOOK_SECRET', 'segredo')
    request = _request('data.id=123', 'id:123;request-id:abc;ts:123;', 'segredo', 'abc')
    assert webhook._assinatura_valida(request, '123')


def test_assinatura_sem_request_id_omite_campo(monkeypatch):
    monkeypatch.setattr(webhook, 'MERCADO_PAGO_WEBHOOK_SECRET', 'segredo')
    request = _request('data.id=123', 'id:123;ts:123;', 'segredo')
    assert webhook._assinatura_valida(request, '123')


def test_assinatura_rejeita_segredo_incorreto(monkeypatch):
    monkeypatch.setattr(webhook, 'MERCADO_PAGO_WEBHOOK_SECRET', 'outro')
    request = _request('data.id=123', 'id:123;request-id:abc;ts:123;', 'segredo', 'abc')
    assert not webhook._assinatura_valida(request, '123')


def test_rota_rejeita_id_do_corpo_diferente_do_assinado(monkeypatch):
    monkeypatch.setattr(webhook, 'MERCADO_PAGO_WEBHOOK_SECRET', 'segredo')
    request = _request('data.id=123&type=payment', 'id:123;request-id:abc;ts:123;', 'segredo', 'abc')
    payload = json.dumps({'type': 'payment', 'user_id': '1', 'data': {'id': '456'}}).encode()

    async def receive():
        return {'type': 'http.request', 'body': payload, 'more_body': False}

    request._receive = receive
    with pytest.raises(HTTPException) as error:
        asyncio.run(webhook.receber_webhook_mercado_pago(request))
    assert error.value.status_code == 400


def test_assinatura_invalida_registra_apenas_diagnostico(monkeypatch, caplog):
    monkeypatch.setattr(webhook, 'MERCADO_PAGO_WEBHOOK_SECRET', 'outro')
    monkeypatch.setattr(webhook, 'MERCADO_PAGO_CLIENT_ID', 'app-correta')
    request = _request('data.id=123&type=payment', 'id:123;request-id:abc;ts:123;', 'segredo', 'abc')
    payload = json.dumps({'type': 'payment', 'user_id': '1', 'data': {'id': '123'},
                          'application_id': 'app-correta', 'live_mode': True}).encode()

    async def receive():
        return {'type': 'http.request', 'body': payload, 'more_body': False}

    request._receive = receive
    with pytest.raises(HTTPException) as error:
        asyncio.run(webhook.receber_webhook_mercado_pago(request))
    assert error.value.status_code == 401
    assert 'modo=producao, aplicacao=corresponde' in caplog.text
    assert 'segredo' not in caplog.text
    assert 'abc' not in caplog.text
