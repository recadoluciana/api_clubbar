import unittest

from app.services.usuarios_operacionais import dominio_disponivel, iniciais_loja


class UsuariosOperacionaisTest(unittest.TestCase):
    def test_iniciais_sem_acentos_e_preposicoes(self):
        self.assertEqual(iniciais_loja("Motor Rock"), "mr")
        self.assertEqual(iniciais_loja("Forró do X"), "fx")

    def test_colisao_usa_identificador_da_loja(self):
        self.assertEqual(dominio_disponivel("Motor Rock", 7, lambda email: email == "b1@mr.com"), "mr7.com")
        self.assertEqual(dominio_disponivel("Motor Rock", 7, lambda email: False), "mr.com")


if __name__ == "__main__":
    unittest.main()
