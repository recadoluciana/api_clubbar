import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from app.routers import lojamercadopago as router
from app.services import mercado_pago_oauth_service as service


@pytest.mark.parametrize('identificador,esperado', [('123', True), ('999', False)])
def test_busca_titular_confere_identidade(monkeypatch, identificador, esperado):
    cliente = AsyncMock()
    cliente.__aenter__.return_value = cliente
    cliente.get.return_value = httpx.Response(200, json={
        'id': identificador, 'first_name': 'Ana', 'last_name': 'Silva',
        'email': 'ana@example.com', 'nickname': 'APELIDO',
    })
    monkeypatch.setattr(service.httpx, 'AsyncClient', MagicMock(return_value=cliente))
    resultado = asyncio.run(service.obter_dados_titular(access_token='token', user_id='123'))
    assert resultado == ({'nome': 'Ana Silva', 'email': 'ana@example.com'} if esperado else {'nome': None, 'email': None})
    assert cliente.get.await_args.args[0].endswith('/users/me')


def test_busca_titular_indisponivel_nao_quebra_integracao(monkeypatch):
    cliente = AsyncMock()
    cliente.__aenter__.return_value = cliente
    cliente.get.return_value = httpx.Response(403, json={'error': 'forbidden'})
    monkeypatch.setattr(service.httpx, 'AsyncClient', MagicMock(return_value=cliente))
    resultado = asyncio.run(service.obter_dados_titular(access_token='token', user_id='123'))
    assert resultado == {'nome': None, 'email': None}


def test_rota_consulta_conta_conectada_somente_quando_solicitado(monkeypatch):
    loja = SimpleNamespace(loja_id=1, organizacao_id=1, provedor_pagamento='MERCADO_PAGO')
    conta = SimpleNamespace(lojamercadopago_id=6, mercadopago_user_id='123', mercadopago_nome='apelido', statusintegracao='ATIVA', access_token_criptografado='cifrado')
    monkeypatch.setattr(router, '_loja_autorizada', MagicMock(return_value=loja))
    monkeypatch.setattr(router, '_config', MagicMock(return_value=conta))
    monkeypatch.setattr(router, '_pendente', MagicMock(return_value=None))
    token = AsyncMock(return_value=('token', conta))
    titular = AsyncMock(return_value={'nome': 'Ana Silva', 'email': 'ana@example.com'})
    monkeypatch.setattr(router, 'obter_token_loja', token)
    monkeypatch.setattr(router, 'obter_dados_titular', titular)
    resultado = asyncio.run(router.consultar_mercado_pago(1, True, {}, MagicMock()))
    assert resultado['mercadopago_titular'] == 'Ana Silva'
    assert resultado['mercadopago_email'] == 'ana@example.com'
    assert 'token' not in resultado.values()
    asyncio.run(router.consultar_mercado_pago(1, False, {}, MagicMock()))
    assert titular.await_count == 1


def test_rota_nao_consulta_dados_antes_da_autorizacao(monkeypatch):
    monkeypatch.setattr(router, '_loja_autorizada', MagicMock(side_effect=HTTPException(403)))
    titular = AsyncMock()
    monkeypatch.setattr(router, 'obter_dados_titular', titular)
    with pytest.raises(HTTPException):
        asyncio.run(router.consultar_mercado_pago(1, True, {}, MagicMock()))
    titular.assert_not_awaited()


def test_rota_preserva_conexao_se_consulta_do_titular_falhar(monkeypatch):
    loja = SimpleNamespace(loja_id=1, organizacao_id=1, provedor_pagamento='MERCADO_PAGO')
    conta = SimpleNamespace(lojamercadopago_id=6, mercadopago_user_id='123', mercadopago_nome='apelido', statusintegracao='ATIVA', access_token_criptografado='cifrado')
    monkeypatch.setattr(router, '_loja_autorizada', MagicMock(return_value=loja))
    monkeypatch.setattr(router, '_config', MagicMock(return_value=conta))
    monkeypatch.setattr(router, '_pendente', MagicMock(return_value=None))
    monkeypatch.setattr(router, 'obter_token_loja', AsyncMock(side_effect=HTTPException(502)))
    resultado = asyncio.run(router.consultar_mercado_pago(1, True, {}, MagicMock()))
    assert resultado['conectada'] is True
    assert resultado.get('mercadopago_titular') is None
    assert resultado.get('mercadopago_email') is None
