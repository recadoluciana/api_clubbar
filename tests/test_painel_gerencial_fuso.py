import unittest
from datetime import date, datetime

from app.routers.painel_gerencial import _inicio_local_em_utc_naive


class PainelGerencialFusoTest(unittest.TestCase):
    def test_inicio_do_dia_brasileiro_e_convertido_para_utc(self):
        self.assertEqual(
            datetime(2026, 8, 7, 3, 0, 0),
            _inicio_local_em_utc_naive(date(2026, 8, 7)),
        )

    def test_venda_utc_da_noite_anterior_fica_dentro_do_dia_brasileiro(self):
        inicio = _inicio_local_em_utc_naive(date(2026, 8, 7))
        fim = _inicio_local_em_utc_naive(date(2026, 8, 8))
        venda = datetime(2026, 8, 8, 1, 58, 42)
        self.assertTrue(inicio <= venda < fim)


if __name__ == "__main__":
    unittest.main()
