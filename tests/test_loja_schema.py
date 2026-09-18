import unittest
from pathlib import Path
from fastapi import HTTPException

import main  # Carrega todos os modelos relacionados antes de configurar os mapeamentos.
from app.models.loja import Loja
from app.models.titularfinanceiro import TitularFinanceiro
from app.routers.lojas import criar_loja


class LojaSchemaTest(unittest.TestCase):
    def test_criacao_direta_de_loja_e_bloqueada(self):
        with self.assertRaises(HTTPException) as erro:
            criar_loja({"role": "SUPERADMIN"})
        self.assertEqual(403, erro.exception.status_code)

    def test_campos_do_onboarding_existem_no_modelo_e_schema(self):
        campos = {
            "tipoloja",
            "atendimentofisico",
            "vendaprodutos",
            "vendaingressos",
        }
        self.assertTrue(campos.issubset(set(Loja.__table__.c.keys())))

        schema = (
            Path(__file__).resolve().parents[1]
            / "scripts"
            / "database"
            / "create"
            / "create_schema.sql"
        ).read_text(encoding="utf-8")
        trecho_loja = schema.split("CREATE TABLE loja (", 1)[1].split(
            ") ENGINE=InnoDB", 1
        )[0]
        for campo in campos:
            self.assertIn(campo, trecho_loja)

    def test_endereco_pode_ser_completado_depois_da_conversao(self):
        for campo in ("nrceploja", "nrendeloja", "estado_id", "cidade_id"):
            self.assertTrue(Loja.__table__.c[campo].nullable)

    def test_loja_possui_identidade_fiscal_do_estabelecimento(self):
        campos = {
            "cpfcnpjloja",
            "cnpjraiz",
            "tipoestabelecimento",
            "nmrazaosocial",
            "titularfinanceiro_id",
        }
        self.assertTrue(campos.issubset(set(Loja.__table__.c.keys())))

        constraints = {item.name for item in Loja.__table__.constraints}
        self.assertIn("fk_loja_titular_org", constraints)
        self.assertTrue(Loja.__table__.c.cpfcnpjloja.unique)

    def test_titular_financeiro_possui_identificadores_unicos(self):
        constraints = {item.name for item in TitularFinanceiro.__table__.constraints}
        self.assertIn("uk_titularfinanceiro_cpfcnpj", constraints)
        self.assertIn("uk_titularfinanceiro_asaas_account", constraints)
        self.assertIn("uk_titularfinanceiro_asaas_wallet", constraints)
        self.assertIn("uk_titularfinanceiro_org_id", constraints)


if __name__ == "__main__":
    unittest.main()
