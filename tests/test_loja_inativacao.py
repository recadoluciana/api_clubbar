import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.routers.lojas import inativar_loja


class LojaInativacaoTest(unittest.TestCase):
    def setUp(self):
        self.loja = SimpleNamespace(loja_id=1, organizacao_id=2, sitloja="ATIVA")
        self.db = Mock()
        self.db.query.return_value.filter.return_value.first.return_value = self.loja

    @patch("app.routers.lojas.validar_permissao_mutacao_loja")
    @patch("app.routers.lojas._pendencias_cancelamento", return_value=[])
    def test_inativa_sem_solicitacao_de_cancelamento(self, pendencias, permissao):
        resultado = inativar_loja(1, self.db, {})

        self.assertEqual(self.loja.sitloja, "INATIVA")
        self.assertEqual(resultado["mensagem"], "Loja inativada com sucesso")
        self.db.commit.assert_called_once()
        self.db.query.assert_called_once()

    @patch("app.routers.lojas.validar_permissao_mutacao_loja")
    @patch("app.routers.lojas._pendencias_cancelamento", return_value=[{}])
    def test_mantem_bloqueio_para_itens_pendentes(self, pendencias, permissao):
        with self.assertRaises(HTTPException) as erro:
            inativar_loja(1, self.db, {})

        self.assertEqual(erro.exception.status_code, 409)
        self.assertEqual(self.loja.sitloja, "ATIVA")
        self.db.commit.assert_not_called()
