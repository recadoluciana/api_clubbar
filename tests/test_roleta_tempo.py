import unittest
from datetime import datetime, timedelta

from pydantic import ValidationError

from app.routers.beneficios_produtos import CampanhaIn


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


if __name__ == "__main__":
    unittest.main()
