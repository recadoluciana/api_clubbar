import unittest
from pathlib import Path

from pydantic import ValidationError

from app.models.leadestabelecimento import LeadEstabelecimento
from app.schemas.portalparceiro import PortalDecisaoUpdate


class PortalDecisaoSchemaTest(unittest.TestCase):
    def test_permite_marcar_decisao_como_analisando(self):
        dados = PortalDecisaoUpdate(decisao="ANALISANDO")

        self.assertEqual(dados.decisao, "ANALISANDO")

    def test_nao_permite_retornar_decisao_para_pendente(self):
        with self.assertRaises(ValidationError):
            PortalDecisaoUpdate(decisao="PENDENTE")

    def test_modelo_e_schema_inicial_possuem_analisando(self):
        self.assertIn(
            "ANALISANDO",
            set(LeadEstabelecimento.__table__.c.decisao.type.enums),
        )
        schema = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "database"
            / "create"
            / "create_schema.sql"
        ).read_text(encoding="utf-8")
        self.assertIn("'ANALISANDO'", schema)


if __name__ == "__main__":
    unittest.main()
