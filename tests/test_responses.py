import unittest
from datetime import datetime

from app.core.responses import datas_operacionais_no_fuso_local


class DatasOperacionaisResponseTests(unittest.TestCase):
    def test_converte_datas_automaticas_utc_para_horario_de_sao_paulo(self):
        resposta = datas_operacionais_no_fuso_local({
            "dtcriacao": "2026-09-19T00:16:06",
            "dtaceite": datetime(2026, 9, 19, 0, 20, 0),
        })

        self.assertEqual(resposta["dtcriacao"], "2026-09-18T21:16:06")
        self.assertEqual(resposta["dtaceite"], "2026-09-18T21:20:00")

    def test_nao_altera_datas_de_negocio_informadas_pelo_usuario(self):
        resposta = datas_operacionais_no_fuso_local({
            "dtinicioevento": "2026-09-19T22:00:00",
            "dtiniciovenda": "2026-09-18T18:00:00",
        })

        self.assertEqual(resposta["dtinicioevento"], "2026-09-19T22:00:00")
        self.assertEqual(resposta["dtiniciovenda"], "2026-09-18T18:00:00")

    def test_converte_datas_em_estruturas_aninhadas(self):
        resposta = datas_operacionais_no_fuso_local({
            "itens": [{"dtultatu": "2026-09-19T01:00:00"}],
        })

        self.assertEqual(resposta["itens"][0]["dtultatu"], "2026-09-18T22:00:00")


if __name__ == "__main__":
    unittest.main()
