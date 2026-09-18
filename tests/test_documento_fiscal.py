import unittest

from app.utils.documento import (
    normalizar_cpf_cnpj,
    raiz_cnpj,
    tipo_estabelecimento_inferido,
)


class DocumentoFiscalTest(unittest.TestCase):
    def test_preserva_letras_de_cnpj_alfanumerico(self):
        self.assertEqual("AA345678000A08", normalizar_cpf_cnpj("AA.345.678/000A-08"))
        self.assertEqual("AA345678", raiz_cnpj("AA.345.678/000A-08"))
        self.assertIsNone(tipo_estabelecimento_inferido("AA.345.678/000A-08"))

    def test_infere_matriz_e_filial_apenas_no_padrao_numerico(self):
        self.assertEqual("MATRIZ", tipo_estabelecimento_inferido("12.345.678/0001-90"))
        self.assertEqual("FILIAL", tipo_estabelecimento_inferido("12.345.678/0002-71"))

    def test_cpf_precisa_ser_numerico(self):
        with self.assertRaises(ValueError):
            normalizar_cpf_cnpj("ABC45678901")


if __name__ == "__main__":
    unittest.main()
