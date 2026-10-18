import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routers.entregas import _validar_data_do_ingresso


class ValidacaoIngressoEventoTest(unittest.TestCase):
    def setUp(self):
        self.item = SimpleNamespace(tipoitem="INGRESSO")
        self.evento = SimpleNamespace(
            evento_id=1,
            dtinicioevento=datetime(2026, 10, 17, 22, 0),
            dtfimevento=datetime(2026, 10, 18, 5, 0),
        )

    def test_ingresso_de_evento_noturno_e_aceito_apos_meia_noite(self):
        with patch(
            "app.routers.entregas._agora_brasil",
            return_value=datetime(2026, 10, 18, 0, 43),
        ):
            _validar_data_do_ingresso(None, self.evento, self.item)

    def test_ingresso_e_recusado_apos_o_encerramento_do_evento(self):
        with patch(
            "app.routers.entregas._agora_brasil",
            return_value=datetime(2026, 10, 18, 5, 0),
        ):
            with self.assertRaises(HTTPException) as erro:
                _validar_data_do_ingresso(None, self.evento, self.item)

        self.assertEqual(409, erro.exception.status_code)
        self.assertIn("evento já encerrado", erro.exception.detail)


if __name__ == "__main__":
    unittest.main()
