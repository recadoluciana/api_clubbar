import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from app.services import mercado_pago_oauth_service as service


class MercadoPagoOAuthTest(unittest.TestCase):
    def test_modo_do_token_na_autorizacao_e_renovacao(self):
        for sandbox in (False, True):
            for renovar in (False, True):
                with self.subTest(sandbox=sandbox, renovar=renovar):
                    cliente = AsyncMock()
                    cliente.__aenter__.return_value = cliente
                    cliente.post.return_value = httpx.Response(
                        200, json={"access_token": "token-ficticio", "user_id": 123}
                    )
                    with patch.object(service, "validar_configuracao_marketplace"), patch.object(
                        service, "MERCADO_PAGO_OAUTH_TEST_TOKEN", sandbox
                    ), patch.object(service.httpx, "AsyncClient", return_value=cliente):
                        if renovar:
                            asyncio.run(service.renovar_tokens(refresh_token="refresh-ficticio"))
                        else:
                            asyncio.run(service.trocar_codigo_por_tokens(code="codigo-ficticio"))
                    dados = cliente.post.call_args.kwargs["data"]
                    self.assertEqual(dados["test_token"], "true" if sandbox else "false")
                    self.assertNotIn("access_token", dados)
