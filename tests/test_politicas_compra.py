import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.routers.politicas import _conteudo, _normalizar_conteudo, PoliticaCompraIn, vigenciar_politica_compra


class PoliticasCompraTest(unittest.TestCase):
    def test_privacidade_sem_parametros_de_compra(self):
        politica = PoliticaCompraIn(versao='1', titulo='Privacidade', tipopolitica='PRIVACIDADE', conteudo='Texto')
        self.assertEqual(politica.tipopolitica, 'PRIVACIDADE')
        self.assertEqual(_conteudo(SimpleNamespace(tipopolitica='PRIVACIDADE', conteudo='')), '')

    def test_nao_publica_privacidade_sem_texto(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = SimpleNamespace(tipopolitica='PRIVACIDADE', conteudo=' ', sitpolitica='RASCUNHO')
        with self.assertRaises(HTTPException) as erro:
            vigenciar_politica_compra(1, {}, db)
        self.assertEqual(erro.exception.status_code, 422)
        db.commit.assert_not_called()

    def test_preserva_texto_editado_da_versao(self):
        politica = SimpleNamespace(conteudo="Texto revisado pelo administrador.")

        self.assertEqual("Texto revisado pelo administrador.", _conteudo(politica))

    def test_conteudo_legado_usa_modelo_dinamico(self):
        politica = SimpleNamespace(
            conteudo="Texto gerado a partir dos parâmetros da política.",
            tipopolitica="PRODUTO",
            qtd_dias_cancelamento=7,
        )

        self.assertIn("7 dias corridos", _conteudo(politica))

    def test_normaliza_quebras_de_linha_sem_perder_paragrafos(self):
        texto = "Primeiro parágrafo.\r\n\r\nSegundo parágrafo.\rTerceiro parágrafo."

        self.assertEqual(
            "Primeiro parágrafo.\n\nSegundo parágrafo.\nTerceiro parágrafo.",
            _normalizar_conteudo(texto),
        )


if __name__ == "__main__":
    unittest.main()
