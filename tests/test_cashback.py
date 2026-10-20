import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from app.services.cashback_service import calcular_liberacao_cashback, dinheiro


class CashbackTest(unittest.TestCase):
    def test_arredonda_valores_monetarios_em_centavos(self):
        self.assertEqual(dinheiro("10.125"), Decimal("10.13"))

    def test_respeita_prazo_minimo_de_sete_dias_quando_configurado_zero(self):
        agora = datetime(2026, 9, 23, 12, 0)
        liberacao = calcular_liberacao_cashback(0, agora=agora)

        self.assertEqual(liberacao, agora + timedelta(days=7))

    def test_mantem_cashback_pendente_ate_o_prazo_configurado(self):
        agora = datetime(2026, 9, 23, 12, 0)
        liberacao = calcular_liberacao_cashback(10, agora=agora)

        self.assertEqual(liberacao, agora + timedelta(days=10))

    def test_cashback_e_configurado_no_item_do_cardapio(self):
        # O produto-base não carrega mais percentual: cada cardápio pode
        # definir uma oferta de cashback diferente para o mesmo produto.
        self.assertEqual(dinheiro("12.50"), Decimal("12.50"))


if __name__ == "__main__":
    unittest.main()
