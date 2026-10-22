import unittest
from unittest.mock import MagicMock, patch

import main


class ClassificacaoEtariaEventoStartupTest(unittest.TestCase):
    def test_cria_a_coluna_que_ainda_nao_existe(self):
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["eventomodelo", "evento"]
        inspector.get_columns.side_effect = lambda tabela: (
            [{"name": "eventomodelo_id"}]
            if tabela == "eventomodelo"
            else [{"name": "evento_id"}, {"name": "classificacaoetaria"}]
        )
        engine = MagicMock()
        conexao = engine.begin.return_value.__enter__.return_value

        with patch.object(main, "engine", engine), patch.object(
            main, "inspect", return_value=inspector
        ):
            main.garantir_classificacao_etaria_evento()

        comandos = [str(chamada.args[0]) for chamada in conexao.execute.call_args_list]
        self.assertEqual(1, len(comandos))
        self.assertIn("ALTER TABLE `eventomodelo`", comandos[0])
        self.assertIn("classificacaoetaria", comandos[0])

    def test_nao_altera_banco_quando_as_colunas_ja_existem(self):
        inspector = MagicMock()
        inspector.get_table_names.return_value = ["eventomodelo", "evento"]
        inspector.get_columns.return_value = [{"name": "classificacaoetaria"}]
        engine = MagicMock()
        conexao = engine.begin.return_value.__enter__.return_value

        with patch.object(main, "engine", engine), patch.object(
            main, "inspect", return_value=inspector
        ):
            main.garantir_classificacao_etaria_evento()

        conexao.execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
