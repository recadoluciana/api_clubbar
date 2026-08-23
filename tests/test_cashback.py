import unittest
from decimal import Decimal

from pydantic import ValidationError

from app.schemas.produto import ProdutoCreate
from app.services.cashback_service import dinheiro


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

    def test_produto_aceita_percentual_opcional(self):
        self.assertIsNone(self._produto().pccashback)
        self.assertEqual(self._produto(Decimal("12.50")).pccashback, Decimal("12.50"))

    def test_produto_rejeita_percentual_fora_do_intervalo(self):
        with self.assertRaises(ValidationError):
            self._produto(Decimal("100.01"))


if __name__ == "__main__":
    unittest.main()
