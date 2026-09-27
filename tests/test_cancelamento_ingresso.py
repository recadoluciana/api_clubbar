import unittest
from datetime import datetime

from app.routers.entregas import _cancelamento_ingresso_permitido, _exige_estorno_asaas


class CancelamentoIngressoTest(unittest.TestCase):
    def test_permite_dentro_de_sete_dias_e_antes_das_quarenta_e_oito_horas(self):
        self.assertTrue(
            _cancelamento_ingresso_permitido(
                datetime(2026, 8, 20, 10),
                datetime(2026, 9, 1, 22),
                agora=datetime(2026, 8, 25, 10),
            )
        )

    def test_bloqueia_depois_de_sete_dias_da_compra(self):
        self.assertFalse(
            _cancelamento_ingresso_permitido(
                datetime(2026, 8, 10, 10),
                datetime(2026, 9, 1, 22),
                agora=datetime(2026, 8, 17, 10, 1),
            )
        )

    def test_bloqueia_quando_faltam_menos_de_quarenta_e_oito_horas(self):
        self.assertFalse(
            _cancelamento_ingresso_permitido(
                datetime(2026, 8, 20, 10),
                datetime(2026, 8, 26, 22),
                agora=datetime(2026, 8, 24, 22, 1),
            )
        )

    def test_ingresso_gratuito_nao_exige_estorno_no_asaas(self):
        self.assertFalse(_exige_estorno_asaas(0))
        self.assertFalse(_exige_estorno_asaas(0.004))
        self.assertTrue(_exige_estorno_asaas(0.01))


if __name__ == "__main__":
    unittest.main()
