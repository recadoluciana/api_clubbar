import unittest
from datetime import datetime, timedelta

from pydantic import ValidationError

from app.routers.beneficios_produtos import CampanhaIn, _periodos_se_sobrepoem


class PromocaoPercentualTest(unittest.TestCase):
    def _dados(self, **sobrescritos):
        dados = {
            "organizacao_id": 1,
            "loja_id": 1,
            "produto_id": 1,
            "tipo": "PERCENTUAL",
            "nmcampanha": "Desconto direto",
            "dthrinicio": datetime(2026, 10, 20, 10, 0),
            "dthrfim": datetime(2026, 10, 21, 10, 0),
            "percentual_desconto": 20,
        }
        dados.update(sobrescritos)
        return dados

    def test_promocao_percentual_exige_um_percentual_valido(self):
        campanha = CampanhaIn(**self._dados())
        self.assertEqual(campanha.percentual_desconto, 20)

        with self.assertRaises(ValidationError):
            CampanhaIn(**self._dados(percentual_desconto=None))

        with self.assertRaises(ValidationError):
            CampanhaIn(**self._dados(percentual_desconto=100))

    def test_campanha_pode_nao_ter_data_final(self):
        campanha = CampanhaIn(**self._dados(dthrfim=None))
        self.assertIsNone(campanha.dthrfim)

    def test_data_final_deve_ser_posterior_ao_inicio(self):
        with self.assertRaises(ValidationError):
            CampanhaIn(**self._dados(dthrfim=datetime(2026, 10, 20, 10, 0)))

    def test_periodos_que_se_cruzam_nao_podem_coexistir(self):
        inicio = datetime(2026, 10, 20, 10, 0)
        fim = inicio + timedelta(hours=2)

        self.assertTrue(
            _periodos_se_sobrepoem(
                inicio,
                fim,
                inicio + timedelta(hours=1),
                fim + timedelta(hours=1),
            )
        )
        self.assertTrue(_periodos_se_sobrepoem(inicio, None, fim, None))

    def test_periodos_separados_podem_coexistir(self):
        inicio = datetime(2026, 10, 20, 10, 0)
        self.assertFalse(
            _periodos_se_sobrepoem(
                inicio,
                inicio + timedelta(hours=1),
                inicio + timedelta(hours=2),
                None,
            )
        )


if __name__ == "__main__":
    unittest.main()
