import unittest
from types import SimpleNamespace

from app.routers.reconciliacao_cancelamentos import _reativar_venda_sem_estorno


class ReconciliacaoCancelamentosTest(unittest.TestCase):
    def test_reativacao_sem_estorno_restabelece_transacao_completa(self):
        venda = SimpleNamespace(sitvenda="CANCELADA")
        pagamento = SimpleNamespace(sitpagvenda="CANCELADO")
        itens = [
            SimpleNamespace(
                sititvenda="CANCELAMENTO_SOLICITADO",
                dtcancelamento="2026-10-14T17:30:00",
                vrreembolso=27.99,
                idreembolso="refund_123",
            ),
            SimpleNamespace(
                sititvenda="CANCELAMENTO_SOLICITADO",
                dtcancelamento=None,
                vrreembolso=None,
                idreembolso=None,
            ),
        ]

        _reativar_venda_sem_estorno(venda, itens, pagamento)

        self.assertEqual("PAGA", venda.sitvenda)
        self.assertEqual("PAGO", pagamento.sitpagvenda)
        for item in itens:
            self.assertEqual("ATIVO", item.sititvenda)
            self.assertIsNone(item.dtcancelamento)
            self.assertIsNone(item.vrreembolso)
            self.assertIsNone(item.idreembolso)


if __name__ == "__main__":
    unittest.main()
