import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from starlette.requests import Request

from app.models.loja import Loja
from app.routers.lojas import dados_loja


class LojaDadosTest(unittest.TestCase):
    def test_dados_loja_seleciona_taxa_minima_que_devolve(self):
        colunas = []
        row = SimpleNamespace(
            loja_id=4, organizacao_id=1, estado_id=1, nmorganizacao="Grupo",
            nmloja="Loja", endloja="Rua", nrceploja="30130000", nrendeloja="10",
            dsbairroloja="Centro", aberto24x7="N", idvalidadeprod="S",
            nrtelloja=None, dsinstaloja=None, dsrefeloja=None,
            complementoloja=None, cidade_id=1, nmcidade="Cidade",
            urllogoloja=None, urlfachadaloja=None,
            vrtaxaprod=5, vrtaxaing=10, vrtaxaminimaingresso=2.99,
        )
        consulta = Mock()
        consulta.join.return_value.outerjoin.return_value.filter.return_value.first.return_value = row
        db = Mock()
        db.query.side_effect = lambda *args: colunas.extend(args) or consulta
        request = Request({"type": "http", "scheme": "https", "server": ("localhost", 443), "path": "/lojas/dados_loja/4", "headers": []})

        saida = dados_loja(4, request, db)

        self.assertTrue(any(coluna is Loja.vrtaxaminimaingresso for coluna in colunas))
        self.assertEqual(saida["vrtaxaminimaingresso"], 2.99)


if __name__ == "__main__":
    unittest.main()
