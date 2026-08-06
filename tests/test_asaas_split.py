import unittest

from unittest.mock import patch

from app.routers.pagamentos import _montar_itens_asaas, _montar_split_clubbar


class AsaasSplitTest(unittest.TestCase):
    def test_soma_taxas_de_produto_e_ingresso_sem_confiar_no_payload(self):
        itens, total, taxa = _montar_itens_asaas([
            {
                "produto_id": 1,
                "nmproduto": "Cerveja",
                "idtipoproduto": "P",
                "qtitcarrinho": 2,
                "vrunitario": 10,
                "vrtaxaitvenda": 1,
            },
            {
                "produto_id": 2,
                "lote_id": 8,
                "nmproduto": "Ingresso",
                "idtipoproduto": "I",
                "qtitcarrinho": 1,
                "vrunitario": 50,
                "vrtaxaitvenda": 5,
            },
        ])

        self.assertEqual(6.0, taxa)
        self.assertEqual(76.0, total)
        self.assertEqual("Taxa de serviço Clubbar", itens[-1]["name"])
        self.assertEqual(6.0, itens[-1]["value"])

    def test_split_transfere_somente_taxa_para_wallet_global(self):
        with patch("app.routers.pagamentos.ASAAS_CLUBBAR_WALLET_ID", "wallet_clubbar"):
            splits = _montar_split_clubbar(6.0, "wallet_loja", "checkout-1")

        self.assertEqual([{
            "walletId": "wallet_clubbar",
            "fixedValue": 6.0,
            "externalReference": "TAXA-checkout-1",
            "description": "Taxa de serviço Clubbar",
        }], splits)
