import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.routers.eventolotes import listar_lotes_disponiveis


class LotesPublicosTest(unittest.TestCase):
    def test_listagem_de_lotes_ativos_nao_exige_usuario(self):
        parametros = inspect.signature(listar_lotes_disponiveis).parameters
        self.assertNotIn("usuario", parametros)
        self.assertEqual({"evento_id", "db"}, set(parametros))

    @patch("app.routers.eventolotes._saida_configuracao")
    @patch("app.routers.eventolotes._carregar_global")
    @patch("app.routers.eventolotes.lote_global_ativo")
    def test_listagem_mantem_setor_esgotado_visivel(
        self,
        lote_global_ativo,
        carregar_global,
        saida_configuracao,
    ):
        db = MagicMock()
        evento = SimpleNamespace(evento_id=10)
        configuracao_esgotada = SimpleNamespace(situacao="ATIVO")
        atual = SimpleNamespace(loteglobal_id=20)
        global_ = SimpleNamespace(configuracoes_setor=[configuracao_esgotada])

        db.query().filter().first.return_value = evento
        lote_global_ativo.return_value = atual
        carregar_global.return_value = global_
        saida_configuracao.return_value = {"nmsetor": "VIP", "qtdisponivel": 0}

        resultado = listar_lotes_disponiveis(10, db)

        self.assertEqual([{"nmsetor": "VIP", "qtdisponivel": 0}], resultado)
        saida_configuracao.assert_called_once_with(db, configuracao_esgotada, evento)


if __name__ == "__main__":
    unittest.main()
