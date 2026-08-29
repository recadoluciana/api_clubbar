import unittest
from pathlib import Path

from app.models.leadparceiro import LeadParceiro, StatusLeadParceiro


class LeadStatusSchemaTest(unittest.TestCase):
    def test_status_de_aprovacao_existe_no_modelo(self):
        self.assertIn(
            "APROVADO_CADASTRO",
            {item.value for item in StatusLeadParceiro},
        )
        self.assertIn(
            "APROVADO_CADASTRO",
            set(LeadParceiro.__table__.c.status.type.enums),
        )

    def test_status_de_aprovacao_existe_no_schema_inicial(self):
        schema = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "database"
            / "create"
            / "create_schema.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("'APROVADO_CADASTRO'", schema)


if __name__ == "__main__":
    unittest.main()
