import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.services.titular_financeiro_service import (
    sincronizar_integracao_asaas_da_loja,
)


class TitularFinanceiroCompartilhadoTest(unittest.TestCase):
    @patch(
        "app.services.titular_financeiro_service.hash_token_webhook",
        return_value="token-hash",
    )
    def test_mesmo_titular_configura_varias_lojas_com_a_mesma_carteira(
        self,
        _hash,
    ):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [None, None]
        titular = SimpleNamespace(
            asaas_account_id="account-1",
            asaas_wallet_id="wallet-1",
            asaas_api_key_criptografada="chave-criptografada",
            status_asaas="APROVADO",
        )

        sincronizar_integracao_asaas_da_loja(
            db,
            SimpleNamespace(loja_id=10, organizacao_id=1),
            titular,
        )
        sincronizar_integracao_asaas_da_loja(
            db,
            SimpleNamespace(loja_id=20, organizacao_id=1),
            titular,
        )

        configuracoes = [chamada.args[0] for chamada in db.add.call_args_list]
        self.assertEqual([10, 20], [item.loja_id for item in configuracoes])
        self.assertTrue(all(item.asaas_wallet_id == "wallet-1" for item in configuracoes))
        self.assertTrue(all(item.statusintegracao == "ATIVA" for item in configuracoes))

    def test_troca_para_titular_nao_ativado_remove_configuracao_anterior(self):
        db = MagicMock()
        configuracao_anterior = SimpleNamespace()
        db.query.return_value.filter.return_value.first.return_value = (
            configuracao_anterior
        )
        titular = SimpleNamespace(
            asaas_account_id=None,
            asaas_wallet_id=None,
            asaas_api_key_criptografada=None,
            status_asaas="NAO_INICIADO",
        )

        sincronizar_integracao_asaas_da_loja(
            db,
            SimpleNamespace(loja_id=10, organizacao_id=1),
            titular,
        )

        db.delete.assert_called_once_with(configuracao_anterior)


if __name__ == "__main__":
    unittest.main()

