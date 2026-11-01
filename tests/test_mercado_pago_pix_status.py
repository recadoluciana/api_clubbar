import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from app.routers import pagamentos
from app.services import venda_gateway_service


@pytest.fixture
def consulta(monkeypatch):
    checkout = SimpleNamespace(
        preference_id='pix-123', payment_id='123', venda_id=None,
        loja_id=1, lojamercadopago_id=7, carrinho_id=22,
        external_reference='pedido-original', status='PENDING', valor=Decimal('5.00'),
    )
    db = Mock()
    token = AsyncMock(return_value=('token-conta-original', None))
    por_id = AsyncMock(return_value={
        'id': 123, 'status': 'approved', 'transaction_amount': 5,
        'external_reference': 'pedido-original',
    })
    por_referencia = AsyncMock(return_value=por_id.return_value.copy())
    criar_venda = AsyncMock(return_value={'venda_id': 42})
    notificar = Mock()
    monkeypatch.setattr(pagamentos, 'obter_token_mercado_pago_loja', token)
    monkeypatch.setattr(pagamentos, 'buscar_pagamento_mercado_pago_por_id', por_id)
    monkeypatch.setattr(pagamentos, 'buscar_pagamento_mercado_pago', por_referencia)
    monkeypatch.setattr(pagamentos, '_notificar_confirmacao_mercado_pago', notificar)
    monkeypatch.setattr(venda_gateway_service, 'criar_venda_paga_por_carrinho_gateway', criar_venda)
    return SimpleNamespace(
        checkout=checkout, db=db, token=token, por_id=por_id,
        por_referencia=por_referencia, criar_venda=criar_venda, notificar=notificar,
    )


def consultar(c):
    return asyncio.run(pagamentos._consultar_status_checkout_mercado_pago(checkout=c.checkout, db=c.db))


@pytest.mark.parametrize('status', ['pending', 'in_process', 'rejected', 'cancelled'])
def test_pix_nao_aprovado_nunca_libera_compra(consulta, status):
    consulta.por_id.return_value['status'] = status
    assert consultar(consulta)['status'] == 'PENDENTE'
    consulta.criar_venda.assert_not_awaited()
    consulta.db.commit.assert_not_called()
    consulta.notificar.assert_not_called()


def test_pix_aprovado_consulta_id_na_conta_original_e_libera_compra(consulta):
    assert consultar(consulta) == {
        'pagamento_id': 'pix-123', 'status': 'PAGO', 'venda_id': 42,
        'cashback_gerado': 0, 'loja_id': 1,
    }
    consulta.token.assert_awaited_once_with(consulta.db, 1, lojamercadopago_id=7)
    consulta.por_id.assert_awaited_once_with(access_token='token-conta-original', payment_id='123')
    consulta.por_referencia.assert_not_awaited()
    assert consulta.criar_venda.await_args.kwargs['checkout_origem'] is consulta.checkout
    assert consulta.criar_venda.await_args.kwargs['gateway'] == 'MERCADO_PAGO'
    assert consulta.checkout.venda_id == 42
    assert consulta.checkout.status == 'APPROVED'
    consulta.db.commit.assert_called_once()


@pytest.mark.parametrize('campo,valor', [
    ('id', 999), ('transaction_amount', 6), ('external_reference', 'outro-pedido'),
])
def test_confirmacao_divergente_nao_libera_compra(consulta, campo, valor):
    consulta.por_id.return_value[campo] = valor
    with pytest.raises(HTTPException) as erro:
        consultar(consulta)
    assert erro.value.status_code == 409
    consulta.criar_venda.assert_not_awaited()
    consulta.db.commit.assert_not_called()


def test_checkout_pro_sem_payment_id_continua_consultando_referencia(consulta):
    consulta.checkout.payment_id = None
    assert consultar(consulta)['status'] == 'PAGO'
    consulta.por_id.assert_not_awaited()
    consulta.por_referencia.assert_awaited_once_with(
        access_token='token-conta-original', external_reference='pedido-original',
    )


def test_pagamento_nao_encontrado_continua_pendente(consulta):
    consulta.por_id.return_value = None
    assert consultar(consulta)['status'] == 'PENDENTE'
    consulta.criar_venda.assert_not_awaited()


def test_consulta_repetida_nao_cria_segunda_venda(consulta):
    assert consultar(consulta)['status'] == 'PAGO'
    assert consultar(consulta)['status'] == 'PAGO'
    consulta.criar_venda.assert_awaited_once()
    consulta.por_id.assert_awaited_once()
