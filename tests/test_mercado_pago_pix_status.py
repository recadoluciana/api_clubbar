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
    monkeypatch.setattr(pagamentos, 'cancelar_uso_pendente', Mock())
    monkeypatch.setattr(venda_gateway_service, 'criar_venda_paga_por_carrinho_gateway', criar_venda)
    return SimpleNamespace(
        checkout=checkout, db=db, token=token, por_id=por_id,
        por_referencia=por_referencia, criar_venda=criar_venda, notificar=notificar,
    )


def consultar(c):
    return asyncio.run(pagamentos._consultar_status_checkout_mercado_pago(checkout=c.checkout, db=c.db))


@pytest.mark.parametrize('status', ['pending', 'in_process'])
def test_pix_nao_aprovado_nunca_libera_compra(consulta, status):
    consulta.por_id.return_value['status'] = status
    assert consultar(consulta)['status'] == 'PENDENTE'
    consulta.criar_venda.assert_not_awaited()
    consulta.db.commit.assert_not_called()
    consulta.notificar.assert_not_called()


@pytest.mark.parametrize('status', ['rejected', 'cancelled'])
def test_pagamento_encerrado_libera_cashback_sem_criar_venda(consulta, status):
    consulta.por_id.return_value['status'] = status
    assert consultar(consulta)['status'] == 'CANCELADO'
    pagamentos.cancelar_uso_pendente.assert_called_once_with(consulta.db, consulta.checkout)
    consulta.criar_venda.assert_not_awaited()
    consulta.db.commit.assert_called_once()


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
        access_token='token-conta-original', external_reference='pedido-original', incluir_pendentes=True,
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


def test_aprovacao_sem_venda_nao_e_reportada_como_compra_concluida(consulta):
    consulta.criar_venda.return_value = {'ok': True}
    with pytest.raises(HTTPException) as erro:
        consultar(consulta)
    assert erro.value.status_code == 409
    assert consulta.checkout.venda_id is None
    consulta.db.commit.assert_not_called()
    consulta.notificar.assert_not_called()


def test_reconciliacao_inclui_checkout_aprovado_sem_venda(monkeypatch):
    from sqlalchemy import create_engine

    db = Mock()
    query = db.query.return_value
    query.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    asyncio.run(pagamentos.reconciliar_pagamentos_pendentes_mercado_pago(
        db=db, payload={'role': 'cliente', 'sub': '2'},
    ))
    filtros = query.filter.call_args.args
    engine = create_engine('sqlite://')
    with engine.begin() as conn:
        conn.exec_driver_sql('CREATE TABLE checkout_mercadopago (cliente_id INTEGER, venda_id INTEGER, status TEXT, carrinho_id INTEGER, dtemailconfirmacao TEXT)')
        conn.exec_driver_sql("INSERT INTO checkout_mercadopago VALUES (2, NULL, 'APPROVED', 22, NULL), (2, NULL, 'CANCELLED', 23, NULL)")
        where = ' AND '.join(str(f.compile(engine, compile_kwargs={'literal_binds': True})) for f in filtros)
        resultado = conn.exec_driver_sql('SELECT carrinho_id FROM checkout_mercadopago WHERE ' + where).scalars().all()
    assert resultado == [22]


def test_reconciliacao_avanca_apos_lote_e_falha_individual(monkeypatch):
    db = Mock()
    query = db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value
    itens = [SimpleNamespace(checkout_mercadopago_id=i, reserva_ingresso_id=None, preference_id=f'pix-{i}', venda_id=None) for i in range(1, 22)]
    query.all.side_effect = [itens[:20], itens[20:], []]
    async def consultar_checkout(*, checkout, db):
        if checkout.checkout_mercadopago_id == 1:
            raise HTTPException(503, 'indisponível')
        return {'status': 'PAGO' if checkout.checkout_mercadopago_id == 21 else 'PENDENTE', 'venda_id': 42}
    consulta = AsyncMock(side_effect=consultar_checkout)
    monkeypatch.setattr(pagamentos, '_consultar_status_checkout_mercado_pago', consulta)
    resultado = asyncio.run(pagamentos.reconciliar_pagamentos_pendentes_mercado_pago(db=db, payload={'role': 'cliente', 'sub': '2'}))
    assert consulta.await_count == 21
    assert resultado['pagamentos_confirmados'] == [{'pagamento_id': 'pix-21', 'venda_id': 42}]
    db.rollback.assert_called_once()


def test_reconciliacao_tenta_email_sem_repetir_confirmacao(monkeypatch):
    db = Mock()
    query = db.query.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value
    checkout = SimpleNamespace(checkout_mercadopago_id=1, reserva_ingresso_id=None, preference_id='pix-1', venda_id=42)
    query.all.side_effect = [[checkout], []]
    consulta = AsyncMock(return_value={'status': 'PAGO', 'venda_id': 42})
    monkeypatch.setattr(pagamentos, '_consultar_status_checkout_mercado_pago', consulta)
    resultado = asyncio.run(pagamentos.reconciliar_pagamentos_pendentes_mercado_pago(db=db, payload={'role': 'cliente', 'sub': '2'}))
    consulta.assert_awaited_once()
    assert resultado['pagamentos_confirmados'] == []


def test_reconciliacao_nao_repete_confirmacao_de_reserva_ja_vendida(monkeypatch):
    from app.routers import reservas_ingressos

    db = Mock()
    checkout_query = Mock()
    reserva_query = Mock()
    db.query.side_effect = [checkout_query, reserva_query]
    checkout = SimpleNamespace(checkout_mercadopago_id=1, reserva_ingresso_id=7, preference_id='pix-1', venda_id=None)
    checkout_query.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.side_effect = [[checkout], []]
    reserva_query.filter.return_value.first.return_value = SimpleNamespace(venda_id=42)
    consulta = AsyncMock(return_value={'status_pagamento': 'PAGO', 'venda_id': 42})
    monkeypatch.setattr(reservas_ingressos, 'status_reserva', consulta)
    resultado = asyncio.run(pagamentos.reconciliar_pagamentos_pendentes_mercado_pago(db=db, payload={'role': 'cliente', 'sub': '2'}))
    consulta.assert_awaited_once()
    assert resultado['pagamentos_confirmados'] == []


def test_webhook_pagamento_tardio_nao_emite_venda_insegura(monkeypatch):
    from app.routers import mercado_pago_webhook as webhook
    checkout = SimpleNamespace(status='CANCELLED', valor=Decimal('5.00'), payment_id='123', venda_id=None, reserva_ingresso_id=None, checkout_mercadopago_id=9)
    config = SimpleNamespace(loja_id=1, lojamercadopago_id=7)
    db = Mock()
    db.query.return_value.filter.return_value.all.return_value = [config]
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = checkout
    monkeypatch.setattr(webhook, 'SessionLocal', lambda: db)
    monkeypatch.setattr(webhook, '_assinatura_valida', lambda *_: True)
    monkeypatch.setattr(webhook, 'obter_token_loja', AsyncMock(return_value=('token', None)))
    monkeypatch.setattr(webhook, 'buscar_pagamento_por_id', AsyncMock(return_value={'status': 'approved', 'transaction_amount': 5, 'external_reference': 'ref'}))
    criar = AsyncMock()
    monkeypatch.setattr(webhook, 'criar_venda_paga_por_carrinho_gateway', criar)
    request = SimpleNamespace(json=AsyncMock(return_value={'type': 'payment', 'data': {'id': '123'}, 'user_id': '10'}), query_params={}, headers={})
    with pytest.raises(HTTPException) as erro:
        asyncio.run(webhook.receber_webhook_mercado_pago(request))
    assert erro.value.status_code == 503
    criar.assert_not_awaited()
    db.rollback.assert_called_once()
    db.close.assert_called_once()
