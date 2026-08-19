import inspect
import unittest

from app.routers.eventolotes import listar_lotes_evento


class LotesPublicosTest(unittest.TestCase):
    def test_listagem_de_lotes_ativos_nao_exige_usuario(self):
        parametros = inspect.signature(listar_lotes_evento).parameters

        self.assertNotIn("usuario", parametros)
        self.assertEqual({"evento_id", "db"}, set(parametros))


if __name__ == "__main__":
    unittest.main()
