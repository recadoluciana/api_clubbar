import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from cryptography.fernet import Fernet

from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial
from app.routers.asaas_webhook import asaas_retorno, asaas_webhook, validar_token_webhook_asaas
from app.routers.pagamentos import status_checkout_asaas
from app.services.asaas_service import criar_checkout_asaas, criar_referencia_checkout_asaas


class QuerySemResultado:
    def filter(self, *args):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return None


class BancoSemCheckout:
    def __init__(self, resultados=None):
        self.consultas = 0
        self.resultados = iter(resultados or [])

    def query(self, *args):
        self.consultas += 1
        query = QuerySemResultado()
        query.first = lambda: next(self.resultados, None)
        return query


class RequisicaoFalsa:
    def __init__(self, token, body):
        self.headers = {"asaas-access-token": token} if token else {}
        self._body = body

    async def json(self):
        return self._body


class RespostaAsaasFalsa:
    status_code = 200
    text = ""

    def json(self):
        return {
            "id": "chk_dev_1",
            "link": "https://sandbox.asaas.test/checkout/chk_dev_1",
            "status": "ACTIVE",
        }


class ClienteHttpFalso:
    ultimo_json = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json, headers):
        type(self).ultimo_json = json
        return RespostaAsaasFalsa()


class AsaasAmbientesTest(unittest.TestCase):
    def test_api_key_da_loja_e_armazenada_criptografada(self):
        chave = Fernet.generate_key().decode()
        with patch("app.core.credential_crypto.ASAAS_CREDENTIAL_ENCRYPTION_KEY", chave):
            criptografada = criptografar_credencial("api-key-secreta-da-loja")
            original = descriptografar_credencial(criptografada)

        self.assertNotIn("api-key-secreta-da-loja", criptografada)
        self.assertEqual("api-key-secreta-da-loja", original)

    def test_referencia_contem_ambiente_e_identificador_unico(self):
        with (
            patch("app.services.asaas_service.APP_ENV", "development"),
            patch("app.services.asaas_service.uuid.uuid4") as uuid4,
        ):
            uuid4.return_value.hex = "abcdef1234567890"
            referencia = criar_referencia_checkout_asaas(42)

        self.assertEqual("CLUBBAR-development-CARRINHO-42-abcdef123456", referencia)

    def test_webhook_exige_token_configurado_e_valido(self):
        with (
            patch("app.routers.asaas_webhook.ASAAS_WEBHOOK_TOKEN", "token-correto"),
            self.assertRaises(HTTPException) as erro,
        ):
            validar_token_webhook_asaas("token-incorreto")

        self.assertEqual(401, erro.exception.status_code)

    def test_webhook_nao_converte_referencia_desconhecida_em_carrinho(self):
        banco = BancoSemCheckout([None, None])
        request = RequisicaoFalsa(
            "token-seguro",
            {
                "event": "CHECKOUT_PAID",
                "checkout": {
                    "id": "checkout_criado_em_outro_ambiente",
                    "externalReference": "CARRINHO-42",
                    "status": "PAID",
                },
            },
        )

        with patch("app.routers.asaas_webhook.ASAAS_WEBHOOK_TOKEN", "token-seguro"):
            resposta = asyncio.run(asaas_webhook(request=request, db=banco))

        self.assertTrue(resposta["ignored"])
        self.assertEqual("Checkout não pertence a este ambiente", resposta["msg"])
        self.assertEqual(2, banco.consultas)

    def test_callback_do_checkout_usa_url_publica_do_ambiente(self):
        ClienteHttpFalso.ultimo_json = None
        with (
            patch(
                "app.services.asaas_service.PUBLIC_API_BASE_URL",
                "https://api-dev.exemplo.com",
            ),
            patch("app.services.asaas_service.httpx.AsyncClient", ClienteHttpFalso),
        ):
            asyncio.run(
                criar_checkout_asaas(
                    valor=10,
                    descricao="Teste",
                    external_reference="CLUBBAR-development-CARRINHO-42-token",
                    carrinho_id=42,
                    api_key="chave-teste",
                )
            )

        callback = ClienteHttpFalso.ultimo_json["callback"]
        self.assertTrue(callback["successUrl"].startswith("https://api-dev.exemplo.com/"))
        self.assertNotIn("api.clubbar.com.br", callback["successUrl"])
        self.assertNotIn("splits", ClienteHttpFalso.ultimo_json)

    def test_checkout_pix_do_partner_configura_qrcode_e_retorno_corretos(self):
        ClienteHttpFalso.ultimo_json = None
        with (
            patch(
                "app.services.asaas_service.PUBLIC_API_BASE_URL",
                "https://api-dev.exemplo.com",
            ),
            patch("app.services.asaas_service.httpx.AsyncClient", ClienteHttpFalso),
        ):
            asyncio.run(
                criar_checkout_asaas(
                    valor=10,
                    descricao="Venda no caixa",
                    external_reference="CLUBBAR-development-CARRINHO-42-token",
                    carrinho_id=42,
                    api_key="chave-teste",
                    billing_types=["PIX"],
                    origem_checkout="PARTNER",
                )
            )

        body = ClienteHttpFalso.ultimo_json
        self.assertEqual(["PIX"], body["billingTypes"])
        for url in body["callback"].values():
            self.assertIn("origem=PARTNER", url)

    def test_callback_de_sucesso_nao_aprova_pagamento(self):
        carrinho = SimpleNamespace(sitcarrinho="ABERTO")
        checkout = SimpleNamespace(checkout_id="chk_1")
        banco = BancoSemCheckout([carrinho, checkout])

        html = asyncio.run(
            asaas_retorno(
                carrinho_id=42,
                acao="sucesso",
                origem="PARTNER",
                db=banco,
            )
        )

        self.assertEqual("ABERTO", carrinho.sitcarrinho)
        self.assertIn("Pagamento em processamento", html)

    def test_consulta_de_status_nao_aprova_pagamento(self):
        checkout = SimpleNamespace(checkout_id="chk_1", status="ACTIVE")
        banco = BancoSemCheckout([checkout])

        resposta = asyncio.run(status_checkout_asaas("chk_1", db=banco))

        self.assertEqual("ACTIVE", checkout.status)
        self.assertEqual("ACTIVE", resposta["status"])


if __name__ == "__main__":
    unittest.main()
