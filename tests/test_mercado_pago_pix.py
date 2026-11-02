import asyncio
import unittest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from app.services import mercado_pago_service as service


class MercadoPagoPixTest(unittest.TestCase):
    def chamar(
        self, resposta, taxa=Decimal('0.05'), *, sandbox=False,
        ambiente='development', email_teste='', email_pagador=' CLIENTE@EXEMPLO.COM ',
    ):
        cliente = AsyncMock()
        cliente.__aenter__.return_value = cliente
        cliente.post.return_value = resposta
        with patch.object(service.httpx, 'AsyncClient', return_value=cliente), patch.object(service, 'PUBLIC_API_BASE_URL', 'https://api.exemplo.com'), patch.object(service, 'APP_ENV', ambiente), patch.object(service, 'MERCADO_PAGO_OAUTH_TEST_TOKEN', sandbox), patch.object(service, 'MERCADO_PAGO_TEST_PAYER_EMAIL', email_teste):
            retorno = asyncio.run(service.criar_pagamento_pix(
                access_token='token-vendedor', external_reference='pedido-teste',
                titulo='PRODUTOS', valor=Decimal('5.00'), valor_taxa_clubbar=taxa,
                email_pagador=email_pagador, documento_pagador='123.456.789-09',
                chave_idempotencia='pedido-pix-unico',
                nome_loja='Forró do X',
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
        self.assertRegex(dados['description'], r'^Venda - Forró do X - \d{2}/\d{2}/\d{4} \d{2}:\d{2}$')
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

    def test_sandbox_substitui_apenas_email_do_payload(self):
        _, chamada = self.chamar(
            httpx.Response(201, json={'id': 123, 'point_of_interaction': {'transaction_data': {'qr_code': 'pix'}}}),
            sandbox=True, email_teste='test_user_comprador@testuser.com',
        )
        self.assertEqual(chamada.kwargs['json']['payer']['email'], 'test_user_comprador@testuser.com')
        self.assertEqual(chamada.kwargs['json']['application_fee'], 0.05)

    def test_sandbox_aceita_cliente_de_teste_sem_override(self):
        _, chamada = self.chamar(
            httpx.Response(201, json={'id': 123, 'point_of_interaction': {'transaction_data': {'qr_code': 'pix'}}}),
            sandbox=True, email_pagador='TEST_USER_COMPRADOR@TESTUSER.COM',
        )
        self.assertEqual(chamada.kwargs['json']['payer']['email'], 'test_user_comprador@testuser.com')

    def test_sandbox_sem_pagador_valido_falha_antes_da_chamada(self):
        for email_teste in ('', 'cliente@exemplo.com'):
            with self.subTest(email_teste=email_teste), patch.object(service.httpx, 'AsyncClient') as cliente:
                with patch.object(service, 'APP_ENV', 'development'), patch.object(service, 'MERCADO_PAGO_OAUTH_TEST_TOKEN', True), patch.object(service, 'MERCADO_PAGO_TEST_PAYER_EMAIL', email_teste):
                    with self.assertRaises(HTTPException) as erro:
                        asyncio.run(service.criar_pagamento_pix(
                            access_token='token', external_reference='pedido', titulo='Produto',
                            valor=Decimal('5'), valor_taxa_clubbar=Decimal('0.05'),
                            email_pagador='cliente@exemplo.com', documento_pagador='12345678909',
                            chave_idempotencia='pedido-pix',
                        ))
                self.assertEqual(erro.exception.status_code, 409)
                self.assertIn('MERCADO_PAGO_TEST_PAYER_EMAIL', erro.exception.detail)
                cliente.assert_not_called()

    def test_producao_nunca_substitui_email_real(self):
        for ambiente in ('production', 'prod'):
            with self.subTest(ambiente=ambiente):
                _, chamada = self.chamar(
                    httpx.Response(201, json={'id': 123, 'point_of_interaction': {'transaction_data': {'qr_code': 'pix'}}}),
                    ambiente=ambiente, sandbox=True, email_teste='test_user_comprador@testuser.com',
                )
                self.assertEqual(chamada.kwargs['json']['payer']['email'], 'cliente@exemplo.com')

    def test_usuarios_invalidos_tem_orientacao_apenas_no_sandbox(self):
        resposta = httpx.Response(400, json={'message': 'Invalid users involved', 'cause': [{'code': 2034}]})
        with self.assertRaises(HTTPException) as erro:
            self.chamar(resposta, sandbox=True, email_teste='test_user_comprador@testuser.com')
        self.assertEqual(erro.exception.status_code, 409)
        self.assertIn('contas de teste diferentes', erro.exception.detail)
        with self.assertRaises(HTTPException) as erro:
            self.chamar(resposta)
        self.assertEqual(erro.exception.status_code, 422)
