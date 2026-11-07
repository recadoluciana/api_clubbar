import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.routers.campanhas_promocionais import CampanhaIn, _loja_permitida, criar


class CampanhasPromocionaisTest(unittest.TestCase):
    def test_gerente_nao_acessa_outro_estabelecimento(self):
        db = MagicMock()
        usuario = {'role': 'usuario', 'organizacao_id': 1, 'loja_id': 3, 'dscargo': 'MANAGER'}
        with self.assertRaises(HTTPException) as erro:
            _loja_permitida(4, usuario, db)
        self.assertEqual(erro.exception.status_code, 403)
        db.query.assert_not_called()

    def test_nao_cadastra_campanha_em_loja_de_outra_empresa(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        usuario = {'role': 'usuario', 'sub': '2', 'organizacao_id': 1, 'dscargo': 'ADMIN'}
        with self.assertRaises(HTTPException) as erro:
            criar(CampanhaIn(loja_id=99, titulo='Oferta', mensagem='Promoção'), usuario, db)
        self.assertEqual(erro.exception.status_code, 404)
        db.commit.assert_not_called()
