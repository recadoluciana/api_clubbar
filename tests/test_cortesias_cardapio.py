import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from pydantic import ValidationError

from app.routers.cardapios import ItemIn
from app.services.cortesia_produto_service import item_eh_cortesia


class CortesiasCardapioTests(unittest.TestCase):
    def test_item_gratuito_exige_limite_e_periodo(self):
        with self.assertRaises(ValidationError):
            ItemIn(produto_id=1, vrpreco=Decimal("0"))

    def test_item_gratuito_com_configuracao_valida(self):
        inicio = datetime(2026, 10, 15, 10, 0)
        item = ItemIn(
            produto_id=1,
            vrpreco=Decimal("6"),
            tipodesconto="PERCENTUAL",
            vrdesconto=Decimal("100"),
            qtcortesia=10,
            dtinicortesia=inicio,
            dtfimcortesia=inicio + timedelta(hours=2),
        )
        self.assertEqual(item.qtcortesia, 10)

    def test_item_pago_limpa_configuracao_de_cortesia(self):
        inicio = datetime(2026, 10, 15, 10, 0)
        item = ItemIn(
            produto_id=1,
            vrpreco=Decimal("6"),
            qtcortesia=10,
            dtinicortesia=inicio,
            dtfimcortesia=inicio + timedelta(hours=2),
        )
        self.assertIsNone(item.qtcortesia)
        self.assertIsNone(item.dtinicortesia)
        self.assertIsNone(item.dtfimcortesia)

    def test_identifica_todas_as_formas_de_cortesia(self):
        self.assertTrue(
            item_eh_cortesia(
                SimpleNamespace(vrpreco=0, tipodesconto="NENHUM", vrdesconto=0)
            )
        )
        self.assertTrue(
            item_eh_cortesia(
                SimpleNamespace(vrpreco=6, tipodesconto="PERCENTUAL", vrdesconto=100)
            )
        )
        self.assertTrue(
            item_eh_cortesia(
                SimpleNamespace(vrpreco=6, tipodesconto="VALOR", vrdesconto=6)
            )
        )
        self.assertFalse(
            item_eh_cortesia(
                SimpleNamespace(vrpreco=6, tipodesconto="PERCENTUAL", vrdesconto=99)
            )
        )


if __name__ == "__main__":
    unittest.main()
