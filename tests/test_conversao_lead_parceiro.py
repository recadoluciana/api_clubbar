import unittest

from app.routers.leadparceiro import (
    CATEGORIAS_PADRAO,
    _senha_inicial_superadmin,
)


class ConversaoLeadParceiroTest(unittest.TestCase):
    def test_senha_usa_seis_digitos_e_seis_caracteres_do_responsavel(self):
        self.assertEqual(
            "123456Carlos",
            _senha_inicial_superadmin("12.345.678/0001-90", "Carlos da Silva"),
        )

    def test_nome_composto_ignora_espacos_na_senha(self):
        self.assertEqual(
            "987654AnaMar",
            _senha_inicial_superadmin("98.765.432/0001-10", "Ana Maria"),
        )

    def test_onboarding_possui_sete_categorias_ordenadas(self):
        self.assertEqual(7, len(CATEGORIAS_PADRAO))
        self.assertEqual("Cervejas", CATEGORIAS_PADRAO[0])
        self.assertEqual("Outros", CATEGORIAS_PADRAO[-1])
        self.assertEqual(7, len(set(CATEGORIAS_PADRAO)))


if __name__ == "__main__":
    unittest.main()
