import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.routers.titularfinanceiro import extrato_mercado_pago


class ExtratoMercadoPagoTest(unittest.IsolatedAsyncioTestCase):
    async def test_manager_nao_acessa_historico_da_conta(self):
        with self.assertRaises(HTTPException) as erro:
            await extrato_mercado_pago(1, 2, db=None, payload={'role': 'usuario', 'dscargo': 'MANAGER', 'organizacao_id': 1})
        self.assertEqual(403, erro.exception.status_code)

    @patch('app.routers.titularfinanceiro.httpx.AsyncClient')
    @patch('app.routers.titularfinanceiro.obter_token_loja', new_callable=AsyncMock)
    @patch('app.routers.titularfinanceiro._resolver_titular')
    async def test_retorna_pagamentos_e_indica_paginacao(self, resolver, token, cliente):
        resolver.return_value = (None, SimpleNamespace(loja_id=2))
        token.return_value = ('segredo', None)
        resposta = SimpleNamespace(is_error=False, json=lambda: {'paging': {'total': 2}, 'results': [{'id': 123, 'transaction_amount': 5, 'status': 'approved'}, {'id': 456, 'transaction_amount': 8, 'status': 'approved'}]})
        cliente.return_value.__aenter__.return_value.get = AsyncMock(return_value=resposta)
        db = unittest.mock.MagicMock()
        db.query.return_value.filter.return_value.all.return_value = [SimpleNamespace(payment_id='123', external_reference='ref')]
        resultado = await extrato_mercado_pago(1, 2, date(2026, 11, 1), date(2026, 11, 7), 0, db, {'role': 'usuario', 'dscargo': 'ADMIN', 'organizacao_id': 1})
        self.assertEqual(resultado['pagamentos'][0]['id'], '123')
        self.assertEqual(len(resultado['pagamentos']), 1)
        self.assertFalse(resultado['possui_mais'])
        self.assertNotIn('segredo', str(resultado))


if __name__ == '__main__':
    unittest.main()
