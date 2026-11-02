from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.models.checkout_mercadopago import CheckoutMercadoPago
from app.routers.entregas import _conta_original_mercado_pago


@pytest.fixture
def db():
    engine = create_engine('sqlite://')
    # The lookup selects the full ORM row; create only the checkout table.
    CheckoutMercadoPago.__table__.create(engine)
    with Session(engine) as session:
        session.execute(text('''INSERT INTO checkout_mercadopago
            (checkout_mercadopago_id, venda_id, loja_id, cliente_id,
             lojamercadopago_id, preference_id, payment_id, external_reference, valor)
            VALUES (1, 7, 1, 3, 2, 'pref', 'payment-7', 'reference-7', 5.50)'''))
        session.commit()
        yield session
    engine.dispose()


def test_recupera_conta_do_checkout_original(db):
    venda = SimpleNamespace(venda_id=7, loja_id=1)
    pagamento = SimpleNamespace(lojamercadopago_id=None, reference_id='reference-7')
    assert _conta_original_mercado_pago(db, venda, pagamento, 'payment-7') == 2
    assert pagamento.lojamercadopago_id == 2


@pytest.mark.parametrize('venda_id,loja_id,payment_id,reference', [
    (8, 1, 'payment-7', 'reference-7'),
    (7, 2, 'payment-7', 'reference-7'),
    (7, 1, 'outro-pagamento', 'reference-7'),
    (7, 1, 'payment-7', 'outra-referencia'),
    (7, 1, 'payment-7', None),
])
def test_recusa_checkout_divergente(db, venda_id, loja_id, payment_id, reference):
    venda = SimpleNamespace(venda_id=venda_id, loja_id=loja_id)
    pagamento = SimpleNamespace(lojamercadopago_id=None, reference_id=reference)
    with pytest.raises(HTTPException) as erro:
        _conta_original_mercado_pago(db, venda, pagamento, payment_id)
    assert erro.value.status_code == 409
    assert pagamento.lojamercadopago_id is None
