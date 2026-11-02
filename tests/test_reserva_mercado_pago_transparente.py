import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from app.services import reserva_mercado_pago_service as service
from app.services import mercado_pago_service as mercado_pago
from app.routers import reservas_ingressos as router
from app.schemas.reserva_ingresso import PagamentoReservaIn
from app.models.checkout_mercadopago import CheckoutMercadoPago
from app.models.loja import Loja
from app.models.cliente import Cliente


def test_prazo_restante_e_calculado_pelo_servidor(monkeypatch):
    monkeypatch.setattr(router, 'beneficios_validos_para_reserva', MagicMock(return_value={}))
    reserva = SimpleNamespace(
        reserva_ingresso_id=2, organizacao_id=1, loja_id=1, cliente_id=3,
        evento_id=4, lote_id=5, lotepreco_id=6, beneficio_id=None,
        tipobeneficio=None, qtreservada=1, vrunitario=Decimal('5'),
        pctaxa=Decimal('8'), vrtaxa=Decimal('2.99'), vrtotal=Decimal('7.99'),
        sitreserva='AGUARDANDO_PAGAMENTO', dtexpiracao=datetime.now() + timedelta(minutes=35),
        venda_id=None,
    )
    resposta = router._saida(MagicMock(), reserva)
    assert 2098 <= resposta['segundos_restantes'] <= 2100


def _dados(expirada=False):
    reserva = SimpleNamespace(
        reserva_ingresso_id=2, venda_id=None, sitreserva='AGUARDANDO_PAGAMENTO',
        dtexpiracao=datetime.now() + timedelta(minutes=-1 if expirada else 10),
    )
    checkout = SimpleNamespace(
        reserva_ingresso_id=2, checkout_mercadopago_id=4, venda_id=None,
        status='PENDING', valor=Decimal('7.99'), payment_id=None,
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.populate_existing.return_value.with_for_update.return_value.first.return_value = reserva
    pagamento = {'id': '99', 'status': 'approved', 'transaction_amount': 7.99}
    return db, reserva, checkout, pagamento


def test_reserva_valida_emite_ingresso(monkeypatch):
    db, _, checkout, pagamento = _dados()
    finalizar = MagicMock(return_value={'venda_id': 10})
    estornar = AsyncMock()
    monkeypatch.setattr(service, 'finalizar_reserva_paga', finalizar)
    monkeypatch.setattr(service, 'estornar_pagamento_mercado_pago', estornar)
    resultado = asyncio.run(service.confirmar_pagamento_reserva_mp(db, checkout=checkout, pagamento=pagamento, access_token='token'))
    assert resultado['venda_id'] == 10
    finalizar.assert_called_once()
    estornar.assert_not_awaited()


def test_pagamento_tardio_estornado_sem_emitir_ingresso(monkeypatch):
    db, reserva, checkout, pagamento = _dados(expirada=True)
    finalizar = MagicMock()
    estornar = AsyncMock(return_value={'status': 'approved'})
    monkeypatch.setattr(service, 'finalizar_reserva_paga', finalizar)
    monkeypatch.setattr(service, 'estornar_pagamento_mercado_pago', estornar)
    resultado = asyncio.run(service.confirmar_pagamento_reserva_mp(db, checkout=checkout, pagamento=pagamento, access_token='token'))
    assert resultado['estornado']
    assert checkout.status == 'REFUNDED'
    assert reserva.sitreserva == 'EXPIRADA'
    finalizar.assert_not_called()
    estornar.assert_awaited_once()


def test_valor_divergente_nao_gera_ingresso_nem_estorno(monkeypatch):
    db, _, checkout, pagamento = _dados()
    pagamento['transaction_amount'] = 6
    estornar = AsyncMock()
    monkeypatch.setattr(service, 'estornar_pagamento_mercado_pago', estornar)
    with pytest.raises(HTTPException) as error:
        asyncio.run(service.confirmar_pagamento_reserva_mp(db, checkout=checkout, pagamento=pagamento, access_token='token'))
    assert error.value.status_code == 409
    estornar.assert_not_awaited()


def test_estorno_falhou_nao_marca_como_estornado(monkeypatch):
    db, reserva, checkout, pagamento = _dados(expirada=True)
    estornar = AsyncMock(side_effect=HTTPException(503, 'Estorno pendente'))
    monkeypatch.setattr(service, 'estornar_pagamento_mercado_pago', estornar)
    with pytest.raises(HTTPException):
        asyncio.run(service.confirmar_pagamento_reserva_mp(db, checkout=checkout, pagamento=pagamento, access_token='token'))
    assert checkout.status == 'PENDING'
    assert reserva.sitreserva == 'AGUARDANDO_PAGAMENTO'


@pytest.mark.parametrize('metodo', ['PIX', 'CREDIT_CARD'])
def test_erro_servidor_mp_nao_e_tratado_como_recusa_definitiva(monkeypatch, metodo):
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = httpx.Response(500, request=httpx.Request('POST', 'https://example.com'))
    monkeypatch.setattr(mercado_pago.httpx, 'AsyncClient', MagicMock(return_value=client))
    comum = dict(access_token='token', external_reference='ref', titulo='INGRESSOS',
                 valor=Decimal('7.99'), valor_taxa_clubbar=Decimal('2.99'), chave_idempotencia='chave')
    with pytest.raises(HTTPException) as error:
        if metodo == 'PIX':
            asyncio.run(mercado_pago.criar_pagamento_pix(**comum, email_pagador='cliente@example.com', documento_pagador='12345678909'))
        else:
            asyncio.run(mercado_pago.criar_pagamento_cartao(**comum, card_token='token', payment_method_id='master'))
    assert error.value.status_code == 502


@pytest.mark.parametrize('metodo', ['PIX', 'CREDIT_CARD'])
def test_reserva_cria_pagamento_direto_com_comissao(monkeypatch, metodo):
    reserva = SimpleNamespace(cliente_id=3, loja_id=1, vrtotal=Decimal('7.99'),
                              vrtaxa=Decimal('2.99'), qtreservada=1,
                              dtexpiracao=datetime.now() + timedelta(minutes=5))
    cliente = SimpleNamespace(emailcliente='cliente@example.com', nrcpfcliente='12345678909')
    conta = SimpleNamespace(lojamercadopago_id=6)
    db = MagicMock()
    loja_query, cliente_query, checkout_query = MagicMock(), MagicMock(), MagicMock()
    class CheckoutFalso:
        reserva_ingresso_id = MagicMock()
        checkout_mercadopago_id = MagicMock()
        status = MagicMock()

        def __new__(cls, **kwargs):
            return SimpleNamespace(**kwargs, venda_id=None, payment_id=None)

    monkeypatch.setattr(router, 'CheckoutMercadoPago', CheckoutFalso)
    loja_query.filter.return_value.first.return_value = SimpleNamespace(provedor_pagamento='MERCADO_PAGO')
    cliente_query.filter.return_value.first.return_value = cliente
    checkout_query.filter.return_value.order_by.return_value.first.return_value = None
    salvo = []

    def adicionar(item):
        item.checkout_mercadopago_id = 7
        salvo.append(item)

    def query(model):
        return {Loja: loja_query, Cliente: cliente_query, CheckoutFalso: checkout_query}[model]

    db.add.side_effect = adicionar
    db.query.side_effect = query
    checkout_query.filter.return_value.with_for_update.return_value.first.side_effect = lambda: salvo[0]
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', MagicMock())
    monkeypatch.setattr(router, '_reserva_para_pagamento', MagicMock(return_value=reserva))
    monkeypatch.setattr(router, 'obter_token_mercado_pago_loja', AsyncMock(return_value=('token', conta)))
    pagamento = {'id': 99, 'status': 'pending', 'point_of_interaction': {'transaction_data': {'qr_code': 'pix-ficticio'}}}
    async def criar(**kwargs):
        assert db.commit.call_count >= 1
        assert salvo[0].status == 'CREATING'
        return pagamento

    pix, cartao = AsyncMock(side_effect=criar), AsyncMock(side_effect=criar)
    monkeypatch.setattr(router, 'criar_pagamento_pix_mercado_pago', pix)
    monkeypatch.setattr(router, 'criar_pagamento_cartao_mercado_pago', cartao)
    payload = PagamentoReservaIn(cliente_id=3, card_token='token-ficticio', payment_method_id='master', payer_email='cliente@example.com')
    resultado = asyncio.run(router.gerar_checkout_reserva_mercado_pago(2, payload, metodo, db, {}))
    criador = pix if metodo == 'PIX' else cartao
    criador.assert_awaited_once()
    assert criador.await_args.kwargs['valor'] == Decimal('7.99')
    assert criador.await_args.kwargs['valor_taxa_clubbar'] == Decimal('2.99')
    assert resultado['pagamento_id'] == salvo[0].external_reference
    if metodo == 'PIX':
        assert resultado['pix_copia_cola'] == 'pix-ficticio'
        assert reserva.dtexpiracao > datetime.now() + timedelta(minutes=34)
        assert resultado['segundos_restantes'] >= 2040


def test_segunda_cobranca_da_mesma_reserva_e_bloqueada(monkeypatch):
    reserva = SimpleNamespace(cliente_id=3, loja_id=1)
    db = MagicMock()
    loja_query, cliente_query, checkout_query = MagicMock(), MagicMock(), MagicMock()
    loja_query.filter.return_value.first.return_value = SimpleNamespace(provedor_pagamento='MERCADO_PAGO')
    cliente_query.filter.return_value.first.return_value = SimpleNamespace()
    checkout_query.filter.return_value.order_by.return_value.first.return_value = SimpleNamespace(status='CREATING')
    db.query.side_effect = lambda model: {Loja: loja_query, Cliente: cliente_query, CheckoutMercadoPago: checkout_query}[model]
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', MagicMock())
    monkeypatch.setattr(router, '_reserva_para_pagamento', MagicMock(return_value=reserva))
    criador = AsyncMock()
    monkeypatch.setattr(router, 'criar_pagamento_cartao_mercado_pago', criador)
    payload = PagamentoReservaIn(cliente_id=3, card_token='token', payment_method_id='master')
    with pytest.raises(HTTPException) as error:
        asyncio.run(router.gerar_checkout_reserva_mercado_pago(2, payload, 'CREDIT_CARD', db, {}))
    assert error.value.status_code == 409
    criador.assert_not_awaited()
