import unittest

from app.models.atracao import Atracao
from app.models.evento import Evento
from app.models.eventoatracao import EventoAtracao  # registra os relacionamentos
from app.models.eventodescricao import EventoDescricao


class ModeloDescricoesTest(unittest.TestCase):
    def test_textos_do_evento_ficam_na_tabela_um_para_um(self):
        self.assertNotIn("dsdescevento", Evento.__table__.c)
        self.assertIn("dsdescevento", EventoDescricao.__table__.c)
        self.assertIn("dspoliticacancelamento", EventoDescricao.__table__.c)
        self.assertIn("dspoliticareembolso", EventoDescricao.__table__.c)
        self.assertIn("dspoliticacashback", EventoDescricao.__table__.c)
        self.assertTrue(EventoDescricao.__table__.c.evento_id.primary_key)

    def test_api_interna_preserva_os_nomes_anteriores(self):
        evento = Evento(
            dsdescevento="Descrição",
            dspoliticacancelamento="Cancelamento",
            dspoliticareembolso="Reembolso",
            dspoliticacashback="Cashback",
        )
        self.assertEqual(evento.dsdescevento, "Descrição")
        self.assertEqual(evento.dspoliticacancelamento, "Cancelamento")
        self.assertEqual(evento.dspoliticareembolso, "Reembolso")
        self.assertEqual(evento.dspoliticacashback, "Cashback")

    def test_texto_da_atracao_fica_na_tabela_um_para_um(self):
        self.assertIn("dsatracao", Atracao.__table__.c)
        self.assertEqual(Atracao(dsatracao="Banda").dsatracao, "Banda")


if __name__ == "__main__":
    unittest.main()
