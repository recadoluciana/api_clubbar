import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.routers.portalparceiro import recuperar_dados_portal
from app.schemas.portalparceiro import PortalRecuperarDados


class PortalRecuperarDadosSchemaTest(unittest.TestCase):
    def test_recuperacao_exige_somente_o_email(self):
        dados = PortalRecuperarDados(email="cliente@clubbar.com.br")

        self.assertEqual("cliente@clubbar.com.br", str(dados.email))
        self.assertNotIn("telefone", PortalRecuperarDados.model_fields)

    def test_envia_os_telefones_encontrados_pelo_email(self):
        lead = SimpleNamespace(
            nmresponsavel="Cliente Clubbar",
            telefone="(35) 99999-0000",
        )

        class Consulta:
            def filter(self, *_):
                return self

            def order_by(self, *_):
                return self

            def all(self):
                return [lead]

        db = SimpleNamespace(query=lambda *_: Consulta())
        dados = PortalRecuperarDados(email="cliente@clubbar.com.br")

        with patch(
            "app.routers.portalparceiro.enviar_dados_portal_lead"
        ) as enviar:
            resposta = recuperar_dados_portal(dados, db)

        enviar.assert_called_once_with(
            "cliente@clubbar.com.br",
            [{"nome": "Cliente Clubbar", "telefone": "(35) 99999-0000"}],
        )
        self.assertIn("novo e-mail foi enviado", resposta["mensagem"])


if __name__ == "__main__":
    unittest.main()
