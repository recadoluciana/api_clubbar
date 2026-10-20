import unittest
from types import SimpleNamespace

from app.models.reserva_ingresso import ReservaIngresso
from app.routers.pagamentos import _sincronizar_checkout_de_reserva_confirmada


class _Query:
    def __init__(self, resultado):
        self.resultado = resultado

    def filter(self, *args):
        return self

    def first(self):
        return self.resultado


class _Db:
    def __init__(self, reserva):
        self.reserva = reserva
        self.commits = 0

    def query(self, model):
        if model is ReservaIngresso:
            return _Query(self.reserva)
        raise AssertionError(f"Consulta inesperada: {model}")

    def commit(self):
        self.commits += 1


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


if __name__ == "__main__":
    unittest.main()
