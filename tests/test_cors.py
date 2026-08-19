import unittest

from fastapi.testclient import TestClient

from main import app


class CorsTest(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def _preflight(self, origem: str):
        return self.client.options(
            "/eventos/proximos",
            headers={
                "Origin": origem,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )

    def test_aceita_dominio_oficial(self):
        resposta = self._preflight("https://app.clubbar.com.br")

        self.assertEqual(200, resposta.status_code)
        self.assertEqual(
            "https://app.clubbar.com.br",
            resposta.headers["access-control-allow-origin"],
        )

    def test_aceita_variacao_do_cliente_no_railway(self):
        origem = "https://clubbarcliente-production-ab12.up.railway.app"
        resposta = self._preflight(origem)

        self.assertEqual(200, resposta.status_code)
        self.assertEqual(origem, resposta.headers["access-control-allow-origin"])

    def test_aceita_flutter_web_em_porta_variavel(self):
        origem = "http://localhost:54321"
        resposta = self._preflight(origem)

        self.assertEqual(200, resposta.status_code)
        self.assertEqual(origem, resposta.headers["access-control-allow-origin"])

    def test_rejeita_origem_fora_do_ecossistema(self):
        resposta = self._preflight("https://exemplo-invalido.com")

        self.assertEqual(400, resposta.status_code)


if __name__ == "__main__":
    unittest.main()
