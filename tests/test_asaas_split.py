import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.routers.pagamentos import _montar_itens_asaas
from app.services.asaas_split_service import montar_split_clubbar, montar_splits_pagamento
from app.services.campanha_doacao_service import carteira_asaas_valida, dados_publicos_campanha


class AsaasSplitTest(unittest.TestCase):
    def test_split_fixo_envia_somente_taxa_para_o_clubbar(self):
        with patch(
            "app.services.asaas_split_service.ASAAS_CLUBBAR_WALLET_ID",
            "wallet-clubbar",
        ):
            split = montar_split_clubbar(5.25)

        self.assertEqual(1, len(split))
        self.assertEqual("wallet-clubbar", split[0]["walletId"])
        self.assertEqual(5.25, split[0]["fixedValue"])
        self.assertNotIn("percentualValue", split[0])

    def test_split_parcelado_usa_valor_total_da_taxa(self):
        with patch(
            "app.services.asaas_split_service.ASAAS_CLUBBAR_WALLET_ID",
            "wallet-clubbar",
        ):
            split = montar_split_clubbar(12, parcelado=True)

        self.assertEqual(12.0, split[0]["totalFixedValue"])
        self.assertNotIn("fixedValue", split[0])

    def test_split_da_doacao_e_adicionado_sem_alterar_taxa_clubbar(self):
        campanha = SimpleNamespace(
            campanhadoacao_id=18,
            asaas_wallet_id="0b763922-aa88-4cbe-a567-e3fe8511fa06",
            percentual_doacao=5,
            nmcampanha="Criança Esperança",
        )
        with patch(
            "app.services.asaas_split_service.ASAAS_CLUBBAR_WALLET_ID",
            "wallet-clubbar",
        ):
            split = montar_splits_pagamento(10, campanha_doacao=campanha)

        self.assertEqual(2, len(split))
        self.assertEqual(10.0, split[0]["fixedValue"])
        self.assertEqual("0b763922-aa88-4cbe-a567-e3fe8511fa06", split[1]["walletId"])
        self.assertEqual(5.0, split[1]["percentualValue"])
        self.assertEqual("DOACAO-18", split[1]["externalReference"])

    def test_split_de_checkout_usa_campo_percentual_do_checkout(self):
        campanha = SimpleNamespace(
            campanhadoacao_id=18,
            asaas_wallet_id="0b763922-aa88-4cbe-a567-e3fe8511fa06",
            percentual_doacao=5,
            nmcampanha="Criança Esperança",
        )
        with patch(
            "app.services.asaas_split_service.ASAAS_CLUBBAR_WALLET_ID",
            "wallet-clubbar",
        ):
            split = montar_splits_pagamento(
                10, campanha_doacao=campanha, para_checkout=True
            )

        self.assertEqual(5.0, split[1]["percentageValue"])
        self.assertNotIn("percentualValue", split[1])

    def test_chave_pix_nao_e_uma_carteira_asaas(self):
        campanha = SimpleNamespace(asaas_wallet_id="esperanca@unesco.org")

        self.assertFalse(carteira_asaas_valida(campanha.asaas_wallet_id))
        self.assertIsNone(dados_publicos_campanha(campanha))

    def test_somente_taxa_de_ingresso_e_cobrada_do_cliente(self):
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

        self.assertEqual(5.0, taxa)
        self.assertEqual(75.0, total)
        self.assertEqual("Taxa de serviço Clubbar", itens[-1]["name"])
        self.assertEqual(5.0, itens[-1]["value"])

    def test_checkout_central_mantem_taxa_no_total_sem_split(self):
        _, total, taxa = _montar_itens_asaas([{
            "produto_id": 1,
            "nmproduto": "Ingresso",
            "idtipoproduto": "I",
            "qtitcarrinho": 1,
            "vrunitario": 50,
            "vrtaxaitvenda": 5,
        }])
        self.assertEqual(55.0, total)
        self.assertEqual(5.0, taxa)
