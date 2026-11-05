import unittest
from app.utils.documento import validar_documento_acesso


class DocumentoAcessoTest(unittest.TestCase):
    def test_documentos_validos(self):
        for entrada, esperado in (("529.982.247-25", "52998224725"), ("12.345.678/0001-95", "12345678000195"), ("12.abc.345/01de-35", "12ABC34501DE35")):
            with self.subTest(entrada=entrada):
                self.assertEqual(validar_documento_acesso(entrada), esperado)

    def test_documentos_invalidos(self):
        for entrada in ("111.111.111-11", "00.000.000/0000-00", "12.ABC.345/01DE-34", "12.345.678/0001-96", "", "52998224725!"):
            with self.subTest(entrada=entrada), self.assertRaises(ValueError):
                validar_documento_acesso(entrada)


if __name__ == "__main__":
    unittest.main()
