import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.routers.titularfinanceiro import extrato_mercado_pago
from app.services.extrato_mercado_pago_service import resumir_vendas_pagamentos


class ExtratoMercadoPagoTest(unittest.IsolatedAsyncioTestCase):
    def test_resumo_exclui_pagamentos_nao_aprovados_e_preserva_centavos(self):
        pagamentos = [
            {'status': 'approved', 'transaction_amount': 5.54, 'transaction_amount_refunded': 0, 'transaction_details': {'net_received_amount': 2.50}},
            {'status': 'approved', 'transaction_amount': 11.08, 'transaction_amount_refunded': 0, 'transaction_details': {'net_received_amount': 5}},
            {'status': 'rejected', 'transaction_amount': 5.54},
            {'status': 'refunded', 'transaction_amount': 3},
        ]
        self.assertEqual(resumir_vendas_pagamentos(pagamentos), {'bruto': 16.62, 'liquido': 7.5, 'reembolso_parcial': False})

    def test_resumo_nao_inventa_liquido_sem_dados_ou_com_reembolso_parcial(self):
        pagamento = {'status': 'approved', 'transaction_amount': 10, 'transaction_amount_refunded': 2, 'transaction_details': {'net_received_amount': 9}}
        self.assertEqual(resumir_vendas_pagamentos([pagamento]), {'bruto': 10.0, 'liquido': None, 'reembolso_parcial': True})
        pagamento['transaction_amount_refunded'] = None
        self.assertIsNone(resumir_vendas_pagamentos([pagamento])['liquido'])
        pagamento['transaction_amount_refunded'] = 0
        pagamento['transaction_details'] = {}
        self.assertIsNone(resumir_vendas_pagamentos([pagamento])['liquido'])

    async def test_manager_nao_acessa_historico_da_conta(self):
        with self.assertRaises(HTTPException) as erro:
            await extrato_mercado_pago(1, 2, db=None, payload={'role': 'usuario', 'dscargo': 'MANAGER', 'organizacao_id': 1})
        self.assertEqual(403, erro.exception.status_code)

    @patch('app.routers.titularfinanceiro.httpx.AsyncClient')
    @patch('app.routers.titularfinanceiro.obter_token_loja', new_callable=AsyncMock)
    @patch('app.routers.titularfinanceiro._resolver_titular')
    async def test_retorna_pagamentos_e_indica_paginacao(self, resolver, token, cliente):
        resolver.return_value = (None, SimpleNamespace(loja_id=2))
        token.return_value = ('segredo', SimpleNamespace(lojamercadopago_id=10, mercadopago_user_id=None))
        resposta = SimpleNamespace(is_error=False, json=lambda: {'paging': {'total': 2}, 'results': [{'id': 123, 'transaction_amount': 5, 'status': 'approved'}, {'id': 456, 'transaction_amount': 8, 'status': 'approved'}]})
        cliente.return_value.__aenter__.return_value.get = AsyncMock(return_value=resposta)
        db = unittest.mock.MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(payment_id='123', external_reference='ref', carrinho_id=5, reserva_ingresso_id=None, venda_id=None)]
        resultado = await extrato_mercado_pago(1, 2, date(2026, 11, 1), date(2026, 11, 7), 0, db, {'role': 'usuario', 'dscargo': 'ADMIN', 'organizacao_id': 1})
        self.assertEqual(resultado['pagamentos'][0]['id'], '123')
        self.assertEqual(resultado['conta_extrato']['id'], 10)
        self.assertEqual(resultado['pagamentos'][0]['tipo_venda'], 'PRODUTO')
        self.assertEqual(len(resultado['pagamentos']), 1)
        self.assertFalse(resultado['possui_mais'])
        self.assertNotIn('segredo', str(resultado))

    @patch('app.routers.titularfinanceiro.httpx.AsyncClient')
    @patch('app.routers.titularfinanceiro.obter_token_loja', new_callable=AsyncMock)
    @patch('app.routers.titularfinanceiro._resolver_titular')
    async def test_resumo_abrange_todas_as_paginas(self, resolver, token, cliente):
        resolver.return_value = (None, SimpleNamespace(loja_id=2))
        token.return_value = ('segredo', SimpleNamespace(lojamercadopago_id=10, mercadopago_user_id=None))
        itens = [{'id': i, 'status': 'approved', 'transaction_amount': 2, 'transaction_amount_refunded': 0, 'transaction_details': {'net_received_amount': 1}} for i in range(1, 52)]
        respostas = [SimpleNamespace(is_error=False, json=lambda parte=parte: {'paging': {'total': 51}, 'results': parte}) for parte in (itens[:50], itens[50:])]
        cliente.return_value.__aenter__.return_value.get = AsyncMock(side_effect=respostas)
        db = unittest.mock.MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(payment_id=str(i), external_reference=None, carrinho_id=5, reserva_ingresso_id=None, venda_id=None) for i in range(1, 52)]
        resultado = await extrato_mercado_pago(1, 2, date(2026, 11, 1), date(2026, 11, 7), 50, db, {'role': 'usuario', 'dscargo': 'ADMIN', 'organizacao_id': 1})
        self.assertEqual(len(resultado['pagamentos']), 1)
        self.assertEqual(resultado['resumo']['bruto'], 102)
        self.assertEqual(resultado['resumo']['liquido'], 51)


if __name__ == '__main__':
    unittest.main()
