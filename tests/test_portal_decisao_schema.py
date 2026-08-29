import unittest

from app.schemas.portalparceiro import PortalDecisaoUpdate


class PortalDecisaoSchemaTest(unittest.TestCase):
    def test_permite_retornar_decisao_para_pendente(self):
        dados = PortalDecisaoUpdate(decisao="PENDENTE")

        self.assertEqual(dados.decisao, "PENDENTE")


if __name__ == "__main__":
    unittest.main()
