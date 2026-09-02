import unittest

from app.models.leadparceiro import LeadParceiro
from app.routers.portalparceiro import _selecionar_lead_login


class PortalLoginLeadSelectionTest(unittest.TestCase):
    def test_localiza_par_correto_quando_email_se_repete(self):
        mais_recente = LeadParceiro(
            leadparceiro_id=5,
            nmresponsavel="Bia",
            email="mesmo@email.com",
            telefone="(35) 99988-1045",
        )
        anterior = LeadParceiro(
            leadparceiro_id=4,
            nmresponsavel="Beatriz",
            email="mesmo@email.com",
            telefone="(35) 99981-1045",
        )

        encontrado = _selecionar_lead_login(
            [mais_recente, anterior], "35999811045"
        )

        self.assertIs(encontrado, anterior)

    def test_retorna_none_quando_telefone_nao_pertence_ao_email(self):
        candidato = LeadParceiro(
            leadparceiro_id=5,
            nmresponsavel="Bia",
            email="lead@email.com",
            telefone="35999881045",
        )

        self.assertIsNone(_selecionar_lead_login([candidato], "35999999999"))


if __name__ == "__main__":
    unittest.main()
