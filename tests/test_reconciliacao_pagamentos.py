import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.models.checkout_asaas import CheckoutAsaas
from app.models.reserva_ingresso import ReservaIngresso
from app.routers.pagamentos import (
    _sincronizar_checkout_de_reserva_confirmada,
    reconciliar_pagamentos_pendentes_asaas,
)


class _Query:
    def __init__(self, resultado):
        self.resultado = resultado

    def filter(self, *args):
        return self

    def first(self):
        return self.resultado

    def order_by(self, *args):
        return self

    def limit(self, *args):
        return self

    def all(self):
        if isinstance(self.resultado, list):
            return self.resultado
        return [self.resultado] if self.resultado is not None else []


class _Db:
    def __init__(self, reserva=None, pendentes=None):
        self.reserva = reserva
        self.pendentes = pendentes or []
        self.commits = 0
        self.rollbacks = 0

    def query(self, model):
        if model is ReservaIngresso:
            return _Query(self.reserva)
        if model is CheckoutAsaas:
            return _Query(self.pendentes)
        raise AssertionError(f"Consulta inesperada: {model}")

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class ReconciliacaoPagamentosTest(unittest.TestCase):
    def test_fecha_checkout_legado_de_reserva_ja_confirmada(self):
        db = _Db(SimpleNamespace(venda_id=87))
        checkout = SimpleNamespace(
            reserva_ingresso_id=42,
            venda_id=None,
            status="PENDING",
            dtconfirmacao=None,
        )

        sincronizado = _sincronizar_checkout_de_reserva_confirmada(db, checkout)

        self.assertTrue(sincronizado)
        self.assertEqual(87, checkout.venda_id)
        self.assertEqual("PAID", checkout.status)
        self.assertIsNotNone(checkout.dtconfirmacao)
        self.assertEqual(1, db.commits)

    def test_nao_altera_checkout_sem_venda_confirmada(self):
        db = _Db(SimpleNamespace(venda_id=None))
        checkout = SimpleNamespace(
            reserva_ingresso_id=42,
            venda_id=None,
            status="PENDING",
            dtconfirmacao=None,
        )

        sincronizado = _sincronizar_checkout_de_reserva_confirmada(db, checkout)

        self.assertFalse(sincronizado)
        self.assertEqual("PENDING", checkout.status)
        self.assertEqual(0, db.commits)

    @patch(
        "app.routers.pagamentos.status_checkout_asaas",
        new_callable=AsyncMock,
    )
    @patch(
        "app.routers.pagamentos._sincronizar_checkout_de_reserva_confirmada",
        return_value=False,
    )
    def test_erro_inesperado_nao_interrompe_reconciliacao(
        self, sincronizar_mock, status_mock
    ):
        status_mock.side_effect = RuntimeError("falha temporária no Asaas")
        checkout = SimpleNamespace(
            checkout_id="pay_123",
            reserva_ingresso_id=None,
        )
        db = _Db(pendentes=[checkout])

        resultado = asyncio.run(
            reconciliar_pagamentos_pendentes_asaas(
                db=db,
                payload={"role": "cliente", "sub": "7"},
            )
        )

        self.assertTrue(resultado["ok"])
        self.assertEqual([], resultado["pagamentos_confirmados"])
        self.assertEqual(1, resultado["pendentes_com_erro"])
        self.assertEqual(1, db.rollbacks)
        sincronizar_mock.assert_called_once_with(db, checkout)
        status_mock.assert_awaited_once_with("pay_123", db)


if __name__ == "__main__":
    unittest.main()
