import unittest
from decimal import Decimal
from fastapi import HTTPException
from app.services.condicoes_comerciais import condicoes_comerciais


class CondicoesComerciaisTest(unittest.TestCase):
    def test_experiencia_sem_mensalidade(self):
        texto, valor = condicoes_comerciais("EXPERIENCIA", None)
        self.assertIsNone(valor)
        self.assertIn("três meses", texto)
        self.assertIn("sem acordo posterior", texto)

    def test_mensalidade_explicitamente_informada(self):
        texto, valor = condicoes_comerciais("MENSALIDADE", "123.45")
        self.assertEqual(Decimal("123.45"), valor)
        self.assertIn("R$ 123,45", texto)

    def test_valores_invalidos_nao_sao_aceitos(self):
        for valor in (None, 0, -1, "NaN", "1.999", "inf"):
            with self.subTest(valor=valor), self.assertRaises(HTTPException):
                condicoes_comerciais("MENSALIDADE", valor)
        with self.assertRaises(HTTPException):
            condicoes_comerciais("EXPERIENCIA", 1)
