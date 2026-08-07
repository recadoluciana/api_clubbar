import unittest
from datetime import datetime
from pydantic import ValidationError
from app.schemas.atracao import EventoAtracaoIn

class EventoAtracaoSchemaTest(unittest.TestCase):
    def test_aceita_programacao_que_atravessa_meia_noite(self):
        item=EventoAtracaoIn(atracao_id=1,dtinicioatracao=datetime(2026,8,7,23),dtfimatracao=datetime(2026,8,8,6))
        self.assertGreater(item.dtfimatracao,item.dtinicioatracao)

    def test_rejeita_fim_anterior_ao_inicio(self):
        with self.assertRaises(ValidationError):
            EventoAtracaoIn(atracao_id=1,dtinicioatracao=datetime(2026,8,8,1),dtfimatracao=datetime(2026,8,7,23))

if __name__ == "__main__": unittest.main()
