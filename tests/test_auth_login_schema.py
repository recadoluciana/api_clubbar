import unittest

from pydantic import ValidationError

from app.schemas.auth import UserLogin


class UserLoginSchemaTest(unittest.TestCase):
    def test_aceita_senha_legada_com_quatro_caracteres(self):
        dados = UserLogin(email="caixa@clubbar.com.br", senha="1234")

        self.assertEqual("caixa@clubbar.com.br", dados.email)
        self.assertEqual("1234", dados.senha)

    def test_rejeita_senha_com_menos_de_quatro_caracteres(self):
        with self.assertRaises(ValidationError):
            UserLogin(email="caixa@clubbar.com.br", senha="123")


if __name__ == "__main__":
    unittest.main()
