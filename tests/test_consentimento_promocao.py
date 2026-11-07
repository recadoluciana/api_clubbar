from types import SimpleNamespace
from unittest.mock import MagicMock
import unittest

from fastapi import HTTPException

from app.routers.consentimento_promocao import PreferenciasPromocao, _cliente, consultar


class ConsentimentoPromocaoTest(unittest.TestCase):
    def test_canais_desativados_por_padrao(self):
        preferencias = PreferenciasPromocao()
        self.assertFalse(preferencias.push)
        self.assertFalse(preferencias.whatsapp)


    def test_parceiro_nao_pode_alterar_preferencias_de_cliente(self):
        with self.assertRaises(HTTPException) as erro:
            _cliente({"role": "usuario", "sub": "1"}, MagicMock())
        self.assertEqual(erro.exception.status_code, 403)


    def test_cliente_sem_autorizacao_na_loja_recebe_canais_desativados(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.side_effect = [
            SimpleNamespace(cliente_id=42),
            SimpleNamespace(loja_id=7),
        ]
        db.query.return_value.filter_by.return_value.first.return_value = None
        resultado = consultar(7, {"role": "cliente", "sub": "42"}, db)
        self.assertEqual(resultado, {"loja_id": 7, "push": False, "whatsapp": False})
        db.query.return_value.filter_by.assert_called_once_with(cliente_id=42, loja_id=7)
