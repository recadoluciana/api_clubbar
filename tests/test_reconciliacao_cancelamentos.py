import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.routers.reconciliacao_cancelamentos import _reativar_venda_sem_estorno, _consultar_estorno, _consultar_estorno_mercado_pago, concluir, reativar


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


class ReconciliacaoMercadoPagoTest(unittest.IsolatedAsyncioTestCase):
    @patch('app.routers.reconciliacao_cancelamentos.consultar_pagamento_asaas', new_callable=AsyncMock)
    @patch('app.routers.reconciliacao_cancelamentos.obter_conta_asaas_da_loja')
    async def test_estorno_asaas_pendente_nao_e_contabilizado_como_concluido(self, conta, consultar):
        conta.return_value = ('chave', None)
        consultar.return_value = {'value': 10, 'refunds': [{'status': 'PENDING', 'value': 10}]}
        resultado = await _consultar_estorno(None, SimpleNamespace(loja_id=3), SimpleNamespace(provedor='ASAAS', idtransacaopagvenda='123', vrpagvenda=10))
        self.assertEqual(0, resultado['valor_estornado'])
        self.assertTrue(resultado['estorno_pendente'])

    async def test_asaas_rejeita_pagamento_de_outro_provedor(self):
        with self.assertRaises(HTTPException) as erro:
            await _consultar_estorno(None, SimpleNamespace(), SimpleNamespace(provedor='MERCADO_PAGO'))
        self.assertEqual(409, erro.exception.status_code)

    @patch('app.routers.reconciliacao_cancelamentos.buscar_pagamento_por_id', new_callable=AsyncMock)
    @patch('app.routers.reconciliacao_cancelamentos.obter_token_loja', new_callable=AsyncMock)
    async def test_so_confirma_quando_pagamento_integralmente_estornado(self, obter_token, buscar):
        obter_token.return_value = ('token', None)
        venda = SimpleNamespace(loja_id=3)
        pagamento = SimpleNamespace(provedor='MERCADO_PAGO', lojamercadopago_id=7, idtransacaopagvenda='123')
        buscar.return_value = {'status': 'approved', 'transaction_amount': 10, 'transaction_amount_refunded': 10}
        self.assertFalse((await _consultar_estorno_mercado_pago(None, venda, pagamento))['estorno_localizado'])
        buscar.return_value = {'status': 'refunded', 'transaction_amount': 10, 'transaction_amount_refunded': 5}
        self.assertFalse((await _consultar_estorno_mercado_pago(None, venda, pagamento))['estorno_localizado'])
        buscar.return_value = {'status': 'refunded', 'transaction_amount': 10, 'transaction_amount_refunded': 10}
        self.assertTrue((await _consultar_estorno_mercado_pago(None, venda, pagamento))['estorno_localizado'])
        obter_token.assert_awaited_with(None, 3, 7)

    @patch('app.routers.reconciliacao_cancelamentos._consultar_estorno_mercado_pago', new_callable=AsyncMock)
    @patch('app.routers.reconciliacao_cancelamentos._venda_em_processamento')
    async def test_nao_finaliza_estorno_nao_confirmado(self, recuperar, consultar):
        item = SimpleNamespace(vrunititvenda=10, qtitvenda=1, vrtaxaitvenda=0, sititvenda='CANCELAMENTO_SOLICITADO')
        recuperar.return_value = (SimpleNamespace(), [item], SimpleNamespace(provedor='MERCADO_PAGO', pagvenda_id=1))
        consultar.return_value = {'estorno_localizado': False, 'valor_estornado': 0}
        with self.assertRaises(HTTPException):
            await concluir(1, {'role': 'usuario', 'dscargo': 'ADMIN', 'organizacao_id': 1}, None)
        self.assertEqual(item.sititvenda, 'CANCELAMENTO_SOLICITADO')

    @patch('app.routers.reconciliacao_cancelamentos._venda_em_processamento')
    async def test_nao_reativa_pagamento_mp_pelo_fluxo_asaas(self, recuperar):
        recuperar.return_value = (SimpleNamespace(), [], SimpleNamespace(provedor='MERCADO_PAGO'))
        with self.assertRaises(HTTPException) as erro:
            await reativar(1, {'role': 'usuario', 'dscargo': 'ADMIN', 'organizacao_id': 1}, None)
        self.assertEqual(409, erro.exception.status_code)


if __name__ == "__main__":
    unittest.main()
