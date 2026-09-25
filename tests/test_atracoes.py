import unittest
from datetime import datetime, timedelta
from types import SimpleNamespace
from pydantic import ValidationError
from app.schemas.atracao import EventoAtracaoIn
from app.routers.eventos import deslocar_programacao_atracoes

class EventoAtracaoSchemaTest(unittest.TestCase):
    def test_aceita_programacao_que_atravessa_meia_noite(self):
        item=EventoAtracaoIn(atracao_id=1,dtinicioatracao=datetime(2026,8,7,23),dtfimatracao=datetime(2026,8,8,6))
        self.assertGreater(item.dtfimatracao,item.dtinicioatracao)

    def test_rejeita_fim_anterior_ao_inicio(self):
        with self.assertRaises(ValidationError):
            EventoAtracaoIn(atracao_id=1,dtinicioatracao=datetime(2026,8,8,1),dtfimatracao=datetime(2026,8,7,23))

    def test_desloca_atracoes_e_preserva_duracao_planejada(self):
        primeira = SimpleNamespace(
            dtinicioatracao=datetime(2026, 10, 11, 20),
            dtfimatracao=datetime(2026, 10, 11, 22),
            nrminutoduracao=120,
        )
        segunda = SimpleNamespace(
            dtinicioatracao=datetime(2026, 10, 11, 22),
            dtfimatracao=datetime(2026, 10, 12),
            nrminutoduracao=120,
        )

        deslocar_programacao_atracoes([primeira, segunda], timedelta(minutes=-30))

        self.assertEqual(primeira.dtinicioatracao, datetime(2026, 10, 11, 19, 30))
        self.assertEqual(primeira.dtfimatracao, datetime(2026, 10, 11, 21, 30))
        self.assertEqual(segunda.dtinicioatracao, datetime(2026, 10, 11, 21, 30))
        self.assertEqual(segunda.dtfimatracao, datetime(2026, 10, 11, 23, 30))

if __name__ == "__main__": unittest.main()
