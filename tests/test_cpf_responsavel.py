import unittest

from app.utils.documento import validar_cpf_responsavel


class ValidarCpfResponsavelTest(unittest.TestCase):
    def test_normaliza_cpf_valido(self):
        self.assertEqual(validar_cpf_responsavel("529.982.247-25"), "52998224725")

    def test_rejeita_documentos_invalidos(self):
        for documento in ("111.111.111-11", "529.982.247-24", "5299822472", "5299822472A", ""):
            with self.subTest(documento=documento), self.assertRaises(ValueError):
                validar_cpf_responsavel(documento)


if __name__ == "__main__":
    unittest.main()
