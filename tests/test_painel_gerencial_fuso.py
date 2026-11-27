import unittest
from datetime import date, datetime, timezone

from unittest.mock import patch

from fastapi import HTTPException

from app.routers.painel_gerencial import (
    _inicio_dia_brasilia,
    _desde_em_brasilia_naive,
    _horario_brasilia_naive,
    _periodo_selecionado,
)


class PainelGerencialFusoTest(unittest.TestCase):
    def test_inicio_do_dia_e_meia_noite_de_brasilia(self):
        self.assertEqual(
            datetime(2026, 8, 7, 0, 0, 0),
            _inicio_dia_brasilia(date(2026, 8, 7)),
        )

    def test_venda_do_inicio_do_dia_seguinte_fica_fora_do_dia_anterior(self):
        inicio = _inicio_dia_brasilia(date(2026, 8, 7))
        fim = _inicio_dia_brasilia(date(2026, 8, 8))
        venda = datetime(2026, 8, 8, 1, 58, 42)
        self.assertFalse(inicio <= venda < fim)

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

    def test_referencia_utc_e_convertida_para_comparacao_em_brasilia(self):
        referencia = datetime(2026, 8, 8, 1, 58, 42, tzinfo=timezone.utc)
        self.assertEqual(datetime(2026, 8, 7, 22, 58, 42), _desde_em_brasilia_naive(referencia))
        self.assertEqual(datetime(2026, 8, 7, 22, 58, 42), _desde_em_brasilia_naive(datetime(2026, 8, 7, 22, 58, 42)))
        self.assertEqual(datetime(2026, 8, 7, 22, 58, 42), _horario_brasilia_naive(referencia))

    @patch("app.routers.painel_gerencial._hoje_local")
    def test_mes_futuro_e_rejeitado(self, hoje_local):
        hoje_local.return_value = date(2026, 8, 18)
        with self.assertRaises(HTTPException) as erro:
            _periodo_selecionado(2026, 9)
        self.assertEqual(422, erro.exception.status_code)


if __name__ == "__main__":
    unittest.main()
