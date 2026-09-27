import unittest
from types import SimpleNamespace

from app.routers.politicas import _conteudo, _normalizar_conteudo


class PoliticasCompraTest(unittest.TestCase):
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
