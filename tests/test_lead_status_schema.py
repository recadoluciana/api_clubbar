import unittest
from pathlib import Path

from app.models.leadparceiro import LeadParceiro, StatusLeadParceiro


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


if __name__ == "__main__":
    unittest.main()
