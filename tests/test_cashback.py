import unittest
from datetime import datetime, timedelta
from decimal import Decimal

from pydantic import ValidationError

from app.schemas.produto import ProdutoCreate
from app.services.cashback_service import calcular_liberacao_cashback, dinheiro


class CashbackTest(unittest.TestCase):
    def _produto(self, percentual=None):
        return ProdutoCreate(
            organizacao_id=1,
            loja_id=1,
            nmproduto="Produto",
            vrprecoprod=Decimal("10.00"),
            pccashback=percentual,
        )

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

    def test_produto_aceita_percentual_opcional(self):
        self.assertIsNone(self._produto().pccashback)
        self.assertEqual(self._produto(Decimal("12.50")).pccashback, Decimal("12.50"))

    def test_produto_rejeita_percentual_fora_do_intervalo(self):
        with self.assertRaises(ValidationError):
            self._produto(Decimal("100.01"))


if __name__ == "__main__":
    unittest.main()
