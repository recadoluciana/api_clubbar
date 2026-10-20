import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace

from app.routers.beneficios_produtos import _proxima_rodada_roleta, _texto_tempo_restante


class RoletaTempoTest(unittest.TestCase):
    def test_informa_liberacao_apos_segundo_giro_na_mesma_janela(self):
        agora = datetime(2026, 10, 20, 15, 30, 0)
        ultimo = SimpleNamespace(dtresgate=agora - timedelta(minutes=10))
        penultimo = SimpleNamespace(dtresgate=agora - timedelta(hours=1))

        proxima = _proxima_rodada_roleta([ultimo, penultimo], agora)

        self.assertEqual(agora + timedelta(hours=23, minutes=50), proxima)
        self.assertEqual("23h 50min 00s", _texto_tempo_restante(proxima, agora))

    def test_nao_bloqueia_giros_separados_por_mais_de_24_horas(self):
        agora = datetime(2026, 10, 20, 15, 30, 0)
        ultimo = SimpleNamespace(dtresgate=agora - timedelta(minutes=10))
        penultimo = SimpleNamespace(dtresgate=agora - timedelta(hours=25))

        self.assertIsNone(_proxima_rodada_roleta([ultimo, penultimo], agora))


if __name__ == "__main__":
    unittest.main()
