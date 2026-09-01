import unittest

from pydantic import ValidationError

from app.schemas.portalparceiro import PortalStatusUpdate


class PortalStatusSchemaTest(unittest.TestCase):
    def test_permite_status_de_decisao(self):
        for status in ("NEGOCIANDO", "ACEITOU_PARCERIA", "RECUSOU_PARCERIA"):
            self.assertEqual(status, PortalStatusUpdate(status=status).status)

    def test_portal_nao_pode_converter_diretamente(self):
        with self.assertRaises(ValidationError):
            PortalStatusUpdate(status="CONVERTIDO")


if __name__ == "__main__":
    unittest.main()
