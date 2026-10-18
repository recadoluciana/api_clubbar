import unittest
from datetime import datetime
from types import SimpleNamespace

from fastapi import HTTPException

from app.services.evento_edicao_service import (
    evento_ja_aconteceu,
    validar_evento_editavel,
)


class EventoEdicaoServiceTest(unittest.TestCase):
    def setUp(self):
        self.evento_noturno = SimpleNamespace(
            dtinicioevento=datetime(2026, 10, 17, 22, 0),
            dtfimevento=datetime(2026, 10, 18, 5, 0),
        )

    def test_evento_noturno_segue_editavel_apos_meia_noite(self):
        agora = datetime(2026, 10, 18, 0, 43)

        self.assertFalse(evento_ja_aconteceu(self.evento_noturno, agora))
        validar_evento_editavel(self.evento_noturno, agora)

    def test_evento_fica_somente_consulta_apos_o_termino(self):
        agora = datetime(2026, 10, 18, 5, 0)

        self.assertTrue(evento_ja_aconteceu(self.evento_noturno, agora))

    def test_evento_sem_termino_usa_janela_operacional_de_seis_horas(self):
        evento = SimpleNamespace(
            dtinicioevento=datetime(2026, 10, 17, 22, 0),
            dtfimevento=None,
        )

        self.assertFalse(evento_ja_aconteceu(evento, datetime(2026, 10, 18, 3, 59)))
        self.assertTrue(evento_ja_aconteceu(evento, datetime(2026, 10, 18, 4, 0)))

    def test_validacao_recusa_evento_encerrado(self):
        with self.assertRaises(HTTPException) as erro:
            validar_evento_editavel(
                SimpleNamespace(
                    dtinicioevento=datetime(2026, 10, 17, 22, 0),
                    dtfimevento=datetime(2026, 10, 18, 5, 0),
                ),
                datetime(2026, 10, 18, 5, 0),
            )

        self.assertEqual(409, erro.exception.status_code)


if __name__ == "__main__":
    unittest.main()
