import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.routers.dispositivos_promocao import DispositivoIn, _hash, registrar, remover


class DispositivosPromocaoTest(unittest.TestCase):
    def test_token_com_espaco_nao_e_aceito(self):
        with self.assertRaises(HTTPException):
            _hash(' token ')

    @patch('app.routers.dispositivos_promocao._cliente')
    def test_registrar_atualiza_dono_do_dispositivo(self, cliente):
        cliente.return_value = SimpleNamespace(cliente_id=12)
        registro = SimpleNamespace(cliente_id=7, token='', plataforma='ios')
        db = MagicMock()
        db.query.return_value.filter_by.return_value.first.return_value = registro
        resultado = registrar(DispositivoIn(token='token-teste', plataforma='android'), {}, db)
        self.assertEqual(resultado, {'registrado': True})
        self.assertEqual(registro.cliente_id, 12)
        self.assertEqual(registro.plataforma, 'android')
        self.assertNotIn('token', resultado)

    @patch('app.routers.dispositivos_promocao._cliente')
    def test_remocao_restrita_ao_cliente(self, cliente):
        cliente.return_value = SimpleNamespace(cliente_id=12)
        db = MagicMock()
        remover(DispositivoIn(token='token-teste', plataforma='ios'), {}, db)
        db.query.return_value.filter_by.assert_called_once_with(
            cliente_id=12, token_hash=_hash('token-teste')
        )


if __name__ == '__main__':
    unittest.main()
