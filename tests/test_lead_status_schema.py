import unittest
from pathlib import Path

from app.models.leadestabelecimento import LeadEstabelecimento, StatusLeadEstabelecimento
from app.models.leadparceiro import LeadParceiro


class LeadStatusSchemaTest(unittest.TestCase):
    def test_status_existe_somente_no_estabelecimento(self):
        self.assertNotIn("status", LeadParceiro.__table__.c)
        self.assertIn("status", LeadEstabelecimento.__table__.c)
        self.assertNotIn("decisao", LeadEstabelecimento.__table__.c)

    def test_status_unico_contem_todo_o_fluxo(self):
        self.assertEqual(
            {
                "NOVO", "CONTATADO", "NEGOCIANDO", "ACEITOU_PARCERIA",
                "CONVERTIDO", "RECUSOU_PARCERIA",
            },
            {item.value for item in StatusLeadEstabelecimento},
        )

    def test_schema_inicial_nao_duplica_status_ou_decisao(self):
        schema = (
            Path(__file__).resolve().parents[1]
            / "scripts" / "database" / "create" / "create_schema.sql"
        ).read_text(encoding="utf-8")
        bloco_lead = schema.split("CREATE TABLE leadparceiro", 1)[1].split(
            "CREATE TABLE leadestabelecimento", 1
        )[0]
        bloco_estabelecimento = schema.split(
            "CREATE TABLE leadestabelecimento", 1
        )[1].split(";", 1)[0]
        self.assertNotIn("status", bloco_lead)
        self.assertNotIn("decisao", bloco_estabelecimento)


if __name__ == "__main__":
    unittest.main()
