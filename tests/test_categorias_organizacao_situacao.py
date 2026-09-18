import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.routers.categorias_organizacao import (
    CategoriaPadraoSituacaoIn,
    alterar_situacao_categoria_organizacao,
)


class CategoriaOrganizacaoSituacaoTest(unittest.TestCase):
    def setUp(self):
        self.categoria = SimpleNamespace(
            categoria_id=5,
            organizacao_id=2,
            categoriapadrao_id=None,
            nmcategoria="Bebidas",
            dsicone="local_drink",
            sitcategoria="ATIVA",
            idordcategoria=1,
        )
        self.db = MagicMock()
        self.db.query.return_value.filter.return_value.first.return_value = self.categoria

    def test_inativar_categoria(self):
        retorno = alterar_situacao_categoria_organizacao(
            2, 5, CategoriaPadraoSituacaoIn(sitcategoria="INATIVA"),
            payload={"organizacao_id": 2}, db=self.db,
        )
        self.assertEqual(retorno["sitcategoria"], "INATIVA")
        self.db.commit.assert_called_once()

    def test_nao_altera_outra_organizacao(self):
        with self.assertRaises(HTTPException) as erro:
            alterar_situacao_categoria_organizacao(
                2, 5, CategoriaPadraoSituacaoIn(sitcategoria="INATIVA"),
                payload={"organizacao_id": 3}, db=self.db,
            )
        self.assertEqual(erro.exception.status_code, 403)
        self.db.commit.assert_not_called()

    def test_situacao_invalida(self):
        with self.assertRaises(HTTPException) as erro:
            alterar_situacao_categoria_organizacao(
                2, 5, CategoriaPadraoSituacaoIn(sitcategoria="PENDENTE"),
                payload={"organizacao_id": 2}, db=self.db,
            )
        self.assertEqual(erro.exception.status_code, 422)
        self.db.commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
