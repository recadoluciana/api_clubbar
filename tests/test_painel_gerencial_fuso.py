import unittest
from datetime import date, datetime

from unittest.mock import patch

from fastapi import HTTPException

from app.routers.painel_gerencial import (
    _inicio_local_em_utc_naive,
    _periodo_selecionado,
)


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

    @patch("app.routers.painel_gerencial._hoje_local")
    def test_mes_atual_termina_no_dia_atual(self, hoje_local):
        hoje_local.return_value = date(2026, 8, 18)
        self.assertEqual(
            (date(2026, 8, 1), date(2026, 8, 18)),
            _periodo_selecionado(2026, 8),
        )

    @patch("app.routers.painel_gerencial._hoje_local")
    def test_mes_anterior_usa_mes_completo(self, hoje_local):
        hoje_local.return_value = date(2026, 8, 18)
        self.assertEqual(
            (date(2026, 2, 1), date(2026, 2, 28)),
            _periodo_selecionado(2026, 2),
        )

    @patch("app.routers.painel_gerencial._hoje_local")
    def test_mes_futuro_e_rejeitado(self, hoje_local):
        hoje_local.return_value = date(2026, 8, 18)
        with self.assertRaises(HTTPException) as erro:
            _periodo_selecionado(2026, 9)
        self.assertEqual(422, erro.exception.status_code)


if __name__ == "__main__":
    unittest.main()
