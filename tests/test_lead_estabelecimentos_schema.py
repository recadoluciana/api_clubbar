import unittest
from pathlib import Path

from app.models.leadestabelecimento import LeadEstabelecimento
from app.models.loja import Loja
from app.models.titularfinanceiro import TitularFinanceiro


ROOT = Path(__file__).resolve().parents[1]


class LeadEstabelecimentosSchemaTest(unittest.TestCase):
    def test_negociacao_pertence_ao_estabelecimento(self):
        colunas = LeadEstabelecimento.__table__.c
        self.assertIn("leadparceiro_id", colunas)
        self.assertIn("decisao", colunas)
        self.assertIn("status", colunas)
        self.assertIn("vrtaxaprod", colunas)
        self.assertIn("vrtaxaing", colunas)

    def test_loja_guarda_origem_e_titular_financeiro(self):
        colunas = Loja.__table__.c
        self.assertIn("leadestabelecimento_id", colunas)
        self.assertIn("titularfinanceiro_id", colunas)

    def test_organizacao_pode_ter_varios_titulares(self):
        self.assertFalse(TitularFinanceiro.__table__.c.organizacao_id.unique)

    def test_schema_vazio_contem_novas_tabelas(self):
        schema = (ROOT / "scripts/database/create/create_schema.sql").read_text(
            encoding="utf-8"
        )
        self.assertIn("CREATE TABLE leadestabelecimento", schema)
        self.assertIn("CREATE TABLE contratolead", schema)
        self.assertNotIn("uq_titularfinanceiro_organizacao", schema)


if __name__ == "__main__":
    unittest.main()
