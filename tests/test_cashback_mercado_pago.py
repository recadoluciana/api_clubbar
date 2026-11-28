from datetime import datetime, timedelta
from decimal import Decimal
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateTable
from main import app as _app  # Registra os relacionamentos ORM da aplicação.

from app.models.cashback_config import CashbackConfig
from app.models.cashback_movimento import CashbackMovimento
from app.models.cashback_saldo import CashbackSaldo
from app.models.checkout_asaas import CheckoutAsaas
from app.models.checkout_mercadopago import CheckoutMercadoPago
from app.models.carrinho import Carrinho
from app.models.cliente import Cliente
from app.models.loja import Loja
from app.models import reserva_ingresso, lojamercadopago  # Registra as tabelas referenciadas.
from app.routers import pagamentos
from app.schemas.pagamentos import PagarNovoIn
from app.services.cashback_service import reservar_uso, vincular_uso_ao_checkout, confirmar_uso, cancelar_uso_pendente


@compiles(BigInteger, 'sqlite')
def _sqlite_integer(_element, _compiler, **_kwargs):
    return 'INTEGER'


@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        for model in (CashbackConfig, CashbackSaldo, CheckoutAsaas, CheckoutMercadoPago, CashbackMovimento, Carrinho, Cliente, Loja):
            connection.execute(CreateTable(model.__table__, include_foreign_key_constraints=[]))
    session = sessionmaker(bind=engine, autoflush=False)()
    session.add_all([
        Loja(loja_id=1, organizacao_id=1, nmloja='Teste', cpfcnpjloja='12345678901', provedor_pagamento='MERCADO_PAGO', vrtaxaprod=5),
        Cliente(cliente_id=2, nmcliente='Cliente', emailcliente='teste@example.com', senhahashcli='teste'),
        Carrinho(carrinho_id=3, cliente_id=2, loja_id=1, organizacao_id=1, sitcarrinho='ABERTO'),
        CashbackConfig(organizacao_id=1, loja_id=1, sitcashback='ATIVO', pcmaxusocompra=30),
        CashbackSaldo(cliente_id=2, organizacao_id=1, loja_id=1, vrdisponivel=10, vrpendente=0),
        CashbackMovimento(cliente_id=2, organizacao_id=1, loja_id=1, tipomovimento='CREDITO',
                          sitcashback='DISPONIVEL', vrbase=30, vrcashback=10,
                          dtvalidade=datetime.now() + timedelta(days=10)),
    ])
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _reservar(db):
    valor, debitos = reservar_uso(db, cliente_id=2, organizacao_id=1, loja_id=1,
                                 total_produtos=Decimal('20'), valor_solicitado=Decimal('6'))
    checkout = CheckoutMercadoPago(cliente_id=2, loja_id=1, carrinho_id=3,
        preference_id='mp-1', external_reference='ref-1', status='PENDING',
        valor=Decimal('14'), vrcashbackusado=valor)
    db.add(checkout)
    db.flush()
    vincular_uso_ao_checkout(db, debitos, checkout)
    db.commit()
    return checkout


def test_pagamento_aprovado_consume_saldo_uma_unica_vez(db):
    checkout = _reservar(db)
    assert db.query(CashbackSaldo).one().vrdisponivel == Decimal('4')
    confirmar_uso(db, checkout, 8)
    db.commit()
    confirmar_uso(db, checkout, 8)
    db.commit()
    debito = db.query(CashbackMovimento).filter_by(tipomovimento='DEBITO').one()
    assert (debito.sitcashback, debito.venda_uso_id, debito.vrcashback) == ('UTILIZADO', 8, Decimal('6'))
    assert db.query(CashbackSaldo).one().vrdisponivel == Decimal('4')


def test_pagamento_cancelado_devolve_saldo_uma_unica_vez(db):
    checkout = _reservar(db)
    cancelar_uso_pendente(db, checkout)
    db.commit()
    cancelar_uso_pendente(db, checkout)
    db.commit()
    assert db.query(CashbackSaldo).one().vrdisponivel == Decimal('10')
    assert db.query(CashbackMovimento).filter_by(tipomovimento='DEBITO').one().sitcashback == 'CANCELADO'


def _preparar_pix(monkeypatch):
    monkeypatch.setattr(pagamentos, 'exigir_cliente_autenticado', lambda *_: None)
    monkeypatch.setattr(pagamentos, 'get_carrinho', lambda *_: {'carrinho_id': 3, 'itens': [{'produto_id': 1}]})
    monkeypatch.setattr(pagamentos, '_recalcular_itens_carrinho', lambda *_: ([{'produto_id': 1}], 20))
    monkeypatch.setattr(pagamentos, '_montar_itens_asaas', lambda *_: ([], 20, 0))
    monkeypatch.setattr(pagamentos, 'obter_token_mercado_pago_loja', AsyncMock(return_value=('token', SimpleNamespace(lojamercadopago_id=9))))
    pix = AsyncMock(return_value={'id': 123, 'point_of_interaction': {'transaction_data': {'qr_code': 'codigo'}}})
    monkeypatch.setattr(pagamentos, 'criar_pagamento_pix_mercado_pago', pix)
    return pix


def test_pix_cobra_total_menos_cashback_e_bloqueia_nova_tentativa(db, monkeypatch):
    pix = _preparar_pix(monkeypatch)
    payload = PagarNovoIn(cliente_id=2, organizacao_id=1, loja_id=1, dsmetodopag='PIX', usar_cashback=True, valor_cashback=6)
    resultado = asyncio.run(pagamentos.pagar_mercado_pago_cliente(payload, db, {}))
    assert resultado['valor'] == 14
    assert pix.await_args.kwargs['valor'] == Decimal('14')
    assert db.query(CashbackSaldo).one().vrdisponivel == Decimal('4')
    assert db.query(CheckoutMercadoPago).one().vrcashbackusado == Decimal('6')
    with pytest.raises(pagamentos.HTTPException) as erro:
        asyncio.run(pagamentos.pagar_mercado_pago_cliente(payload, db, {}))
    assert erro.value.status_code == 409
    pix.assert_awaited_once()


def test_falha_inconclusiva_mantem_reserva_para_conciliacao(db, monkeypatch):
    pix = _preparar_pix(monkeypatch)
    pix.side_effect = pagamentos.HTTPException(502, 'Resposta do provedor desconhecida')
    payload = PagarNovoIn(cliente_id=2, organizacao_id=1, loja_id=1, dsmetodopag='PIX', usar_cashback=True, valor_cashback=6)
    with pytest.raises(pagamentos.HTTPException):
        asyncio.run(pagamentos.pagar_mercado_pago_cliente(payload, db, {}))
    assert db.query(CheckoutMercadoPago).one().status == 'CREATING'
    assert db.query(CashbackSaldo).one().vrdisponivel == Decimal('4')
    assert db.query(CashbackMovimento).filter_by(tipomovimento='DEBITO').one().sitcashback == 'PENDENTE'


def test_recusa_do_provedor_devolve_reserva(db, monkeypatch):
    pix = _preparar_pix(monkeypatch)
    pix.side_effect = pagamentos.HTTPException(422, 'Pagamento recusado')
    payload = PagarNovoIn(cliente_id=2, organizacao_id=1, loja_id=1, dsmetodopag='PIX', usar_cashback=True, valor_cashback=6)
    with pytest.raises(pagamentos.HTTPException):
        asyncio.run(pagamentos.pagar_mercado_pago_cliente(payload, db, {}))
    assert db.query(CheckoutMercadoPago).one().status == 'REJECTED'
    assert db.query(CashbackSaldo).one().vrdisponivel == Decimal('10')
    assert db.query(CashbackMovimento).filter_by(tipomovimento='DEBITO').one().sitcashback == 'CANCELADO'


def test_cartao_cobra_valor_com_desconto(db, monkeypatch):
    _preparar_pix(monkeypatch)
    cartao = AsyncMock(return_value={'id': 456, 'status': 'approved'})
    monkeypatch.setattr(pagamentos, 'criar_pagamento_cartao_mercado_pago', cartao)
    payload = PagarNovoIn(cliente_id=2, organizacao_id=1, loja_id=1, dsmetodopag='CREDIT_CARD',
                          card_token='token', payment_method_id='visa', usar_cashback=True, valor_cashback=6)
    resultado = asyncio.run(pagamentos.pagar_mercado_pago_cliente(payload, db, {}))
    assert resultado['valor_cobrado'] == 14
    assert cartao.await_args.kwargs['valor'] == Decimal('14')
    assert db.query(CheckoutMercadoPago).one().vrcashbackusado == Decimal('6')
    assert db.query(CashbackSaldo).one().vrdisponivel == Decimal('4')
