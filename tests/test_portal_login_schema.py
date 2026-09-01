import unittest

from pydantic import ValidationError

from app.schemas.portalparceiro import PortalLoginLead


class PortalLoginLeadSchemaTest(unittest.TestCase):
    def test_aceita_email_e_telefone_validos(self):
        dados = PortalLoginLead(email="lead@clubbar.com.br", telefone="(11) 99999-8888")
        self.assertEqual("lead@clubbar.com.br", str(dados.email))

    def test_telefone_e_obrigatorio(self):
        with self.assertRaises(ValidationError):
            PortalLoginLead(email="lead@clubbar.com.br", telefone="")


if __name__ == "__main__":
    unittest.main()
