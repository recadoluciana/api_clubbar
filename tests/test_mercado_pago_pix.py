import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from app.services import mercado_pago_service as service


class MercadoPagoPixTest(unittest.TestCase):
    def chamar(self, resposta, taxa=Decimal('0.05')):
        cliente = AsyncMock()
        cliente.__aenter__.return_value = cliente
        cliente.post.return_value = resposta
        with patch.object(service.httpx, 'AsyncClient', return_value=cliente), patch.object(service, 'PUBLIC_API_BASE_URL', 'https://api.exemplo.com'):
            retorno = asyncio.run(service.criar_pagamento_pix(
                access_token='token-vendedor', external_reference='pedido-teste',
                titulo='PRODUTOS', valor=Decimal('5.00'), valor_taxa_clubbar=taxa,
                email_pagador=' CLIENTE@EXEMPLO.COM ', documento_pagador='123.456.789-09',
                chave_idempotencia='pedido-pix-unico',
            ))
        return retorno, cliente.post.call_args

    def test_pix_com_split_e_qr_code(self):
        resposta = httpx.Response(201, json={'id': 123, 'point_of_interaction': {'transaction_data': {'qr_code': 'codigo-pix'}}})
        retorno, chamada = self.chamar(resposta)
        self.assertEqual(retorno['id'], 123)
        self.assertTrue(chamada.args[0].endswith('/v1/payments'))
        self.assertEqual(chamada.kwargs['headers']['Authorization'], 'Bearer token-vendedor')
        self.assertEqual(chamada.kwargs['headers']['X-Idempotency-Key'], 'pedido-pix-unico')
        dados = chamada.kwargs['json']
        self.assertEqual(dados['application_fee'], 0.05)
        self.assertEqual(dados['transaction_amount'], 5.0)
        self.assertEqual(dados['payment_method_id'], 'pix')
        self.assertEqual(dados['payer']['email'], 'cliente@exemplo.com')
        self.assertEqual(dados['payer']['identification']['number'], '12345678909')
        self.assertEqual(dados['notification_url'], 'https://api.exemplo.com/mercado-pago/webhook')

    def test_sem_comissao_nao_envia_taxa(self):
        _, chamada = self.chamar(httpx.Response(201, json={'id': 123, 'point_of_interaction': {'transaction_data': {'qr_code': 'pix'}}}), Decimal('0'))
        self.assertNotIn('application_fee', chamada.kwargs['json'])

    def test_recusa_do_split_nao_e_sucesso(self):
        with self.assertRaises(HTTPException) as erro:
            self.chamar(httpx.Response(400, json={'message': 'application_fee rejected', 'cause': [{'code': 2059}]}))
        self.assertEqual(erro.exception.status_code, 422)

    def test_resposta_sem_qr_nao_e_sucesso(self):
        with self.assertRaises(HTTPException) as erro:
            self.chamar(httpx.Response(201, json={'id': 123}))
        self.assertEqual(erro.exception.status_code, 502)
