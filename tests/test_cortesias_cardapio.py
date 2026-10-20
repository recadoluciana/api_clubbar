import unittest
from decimal import Decimal
from types import SimpleNamespace

from pydantic import ValidationError

from app.routers.cardapios import ItemIn
from app.services.cortesia_produto_service import item_eh_cortesia


class CortesiasCardapioTests(unittest.TestCase):
    def test_item_do_cardapio_exige_preco_positivo(self):
        with self.assertRaises(ValidationError):
            ItemIn(produto_id=1, vrpreco=Decimal("0"))

    def test_item_do_cardapio_nao_permite_desconto_total(self):
        with self.assertRaises(ValidationError):
            ItemIn(
                produto_id=1,
                vrpreco=Decimal("6"),
                tipodesconto="PERCENTUAL",
                vrdesconto=Decimal("100"),
            )

    def test_cortesia_e_controlada_por_campanha(self):
        item = SimpleNamespace(vrpreco=6, tipodesconto="PERCENTUAL", vrdesconto=99)
        self.assertFalse(item_eh_cortesia(item))


if __name__ == "__main__":
    unittest.main()
