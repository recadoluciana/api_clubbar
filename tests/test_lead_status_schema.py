import unittest
from pathlib import Path

from pydantic import ValidationError

from app.models.leadparceiro import LeadParceiro, StatusLeadParceiro
from app.schemas.leadparceiro import LeadParceiroUpdate


class LeadStatusSchemaTest(unittest.TestCase):
    def test_status_de_decisao_existem_no_modelo(self):
        self.assertIn(
            "ACEITOU_PARCERIA",
            {item.value for item in StatusLeadParceiro},
        )
        self.assertIn(
            "ACEITOU_PARCERIA",
            set(LeadParceiro.__table__.c.status.type.enums),
        )
        self.assertIn(
            "RECUSOU_PARCERIA",
            {item.value for item in StatusLeadParceiro},
        )

    def test_status_de_decisao_existem_no_schema_inicial(self):
        schema = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "database"
            / "create"
            / "create_schema.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("'ACEITOU_PARCERIA'", schema)
        self.assertIn("'RECUSOU_PARCERIA'", schema)

    def test_edicao_comum_nao_pode_marcar_lead_como_convertido(self):
        with self.assertRaises(ValidationError):
            LeadParceiroUpdate(status="CONVERTIDO")

    def test_edicao_comum_mantem_status_operacionais(self):
        for status in (
            "NOVO",
            "CONTATADO",
            "NEGOCIANDO",
            "ACEITOU_PARCERIA",
            "RECUSOU_PARCERIA",
        ):
            self.assertEqual(status, LeadParceiroUpdate(status=status).status)


if __name__ == "__main__":
    unittest.main()
