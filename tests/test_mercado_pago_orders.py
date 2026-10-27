import asyncio
import unittest
from decimal import Decimal
from unittest.mock import patch

from app.services import mercado_pago_service


class _RespostaMercadoPago:
    is_error = False
    status_code = 201

    @staticmethod
    def json():
        return {
            "id": "ORD_TESTE_123",
            "checkout_url": "https://www.mercadopago.com.br/checkout/v1/redirect?order_id=ORD_TESTE_123",
        }


class _ClienteMercadoPago:
    def __init__(self):
        self.chamada = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    async def post(self, url, *, headers, json):
        self.chamada = {"url": url, "headers": headers, "json": json}
        return _RespostaMercadoPago()


class MercadoPagoOrdersTest(unittest.TestCase):
    def test_order_pix_configura_retorno_automatico_e_split(self):
        cliente = _ClienteMercadoPago()
        with (
            patch.object(mercado_pago_service, "PUBLIC_CLIENT_BASE_URL", "https://app.clubbar.com.br"),
            patch.object(mercado_pago_service.httpx, "AsyncClient", return_value=cliente),
        ):
            retorno = asyncio.run(
                mercado_pago_service.criar_order_checkout_pro(
                    access_token="APP_USR_TESTE",
                    external_reference="MP-PRODUCTION-CLIENT-85-abc123",
                    titulo="Produtos - Bar da Cida",
                    itens=[
                        {
                            "title": "Água",
                            "quantity": 1,
                            "unit_price": Decimal("5.25"),
                            "description": "campo que não deve ir para a Order",
                        }
                    ],
                    valor_total=Decimal("5.25"),
                    valor_taxa_clubbar=Decimal("0.26"),
                    email_pagador="CLIENTE@EXEMPLO.COM ",
                )
            )

        self.assertEqual(retorno["id"], "ORD_TESTE_123")
        self.assertEqual(
            cliente.chamada["url"],
            f"{mercado_pago_service.MERCADO_PAGO_API_BASE_URL}/v1/orders",
        )
        self.assertEqual(cliente.chamada["headers"]["Authorization"], "Bearer APP_USR_TESTE")
        self.assertTrue(cliente.chamada["headers"]["X-Idempotency-Key"])

        dados = cliente.chamada["json"]
        self.assertEqual(dados["type"], "online")
        self.assertEqual(dados["processing_mode"], "manual")
        self.assertEqual(dados["capture_mode"], "automatic_async")
        self.assertEqual(dados["total_amount"], "5.25")
        self.assertEqual(dados["marketplace_fee"], "0.26")
        self.assertEqual(dados["payer"], {"email": "cliente@exemplo.com"})
        self.assertEqual(
            dados["items"],
            [{"title": "Água", "quantity": 1, "unit_price": "5.25"}],
        )
        self.assertEqual(
            dados["config"]["online"]["success_url"],
            "https://app.clubbar.com.br/?pagamento=mercado_pago&acao=sucesso&referencia=MP-PRODUCTION-CLIENT-85-abc123",
        )
        self.assertEqual(dados["config"]["online"]["auto_return"], "approved")


if __name__ == "__main__":
    unittest.main()
