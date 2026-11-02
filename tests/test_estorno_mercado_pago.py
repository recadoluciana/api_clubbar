import asyncio
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from app.services import mercado_pago_service as service


def _cliente(monkeypatch, resposta):
    cliente = MagicMock()
    cliente.__aenter__ = AsyncMock(return_value=cliente)
    cliente.__aexit__ = AsyncMock(return_value=False)
    cliente.post = AsyncMock(return_value=resposta)
    monkeypatch.setattr(service.httpx, 'AsyncClient', lambda **kwargs: cliente)
    return cliente


def test_estorno_integral_sem_corpo_e_com_chave_idempotente(monkeypatch):
    cliente = _cliente(monkeypatch, httpx.Response(201, json={'id': 42, 'status': 'approved'}))
    resultado = asyncio.run(service.estornar_pagamento_mercado_pago(access_token='segredo', payment_id='123', venda_id=7))
    assert resultado['id'] == 42
    chamada = cliente.post.call_args
    assert chamada.args[0].endswith('/v1/payments/123/refunds')
    assert 'json' not in chamada.kwargs and 'content' not in chamada.kwargs
    assert chamada.kwargs['headers']['X-Idempotency-Key']


def test_recusa_registra_diagnostico_sem_credencial(monkeypatch, caplog):
    resposta = httpx.Response(400, json={'error': 'bad_request', 'message': 'insufficient funds', 'cause': [{'code': 123}]}, headers={'x-request-id': 'req-123'})
    _cliente(monkeypatch, resposta)
    with pytest.raises(HTTPException) as erro:
        asyncio.run(service.estornar_pagamento_mercado_pago(access_token='segredo', payment_id='123', venda_id=7))
    assert erro.value.status_code == 409
    assert 'insufficient funds' in caplog.text
    assert 'req-123' in caplog.text
    assert 'segredo' not in caplog.text


def test_recusa_saldo_exibe_motivo_e_registra_descricao(monkeypatch, caplog):
    resposta = httpx.Response(400, json={'message': "Collector hasn't enough available money", 'cause': [{'code': 2031, 'description': "Collector hasn't enough available money"}]})
    _cliente(monkeypatch, resposta)
    with pytest.raises(HTTPException) as erro:
        asyncio.run(service.estornar_pagamento_mercado_pago(access_token='segredo', payment_id='123', venda_id=7))
    assert 'saldo insuficiente' in erro.value.detail
    assert "Collector hasn't enough available money" in caplog.text
