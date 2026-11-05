import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from app.routers.cardapios import DadosProdutoIn, FotoProdutoIn, alterar_dados_produto, alterar_foto_produto


class EdicaoFotoProdutoTest(unittest.TestCase):
    def setUp(self):
        self.produto = SimpleNamespace(nmproduto='Água', dsproduto='Gelada', vrprecopadrao=Decimal('5'),
                                       sitproduto='ATIVO', urlfotoproduto='/foto-antiga.png', skuproduto='SKU')
        self.db = MagicMock()
        self.db.query.return_value.filter.return_value.first.return_value = self.produto
        self.patch_auth = patch('app.routers.cardapios._validar_organizacao_do_produto')
        self.patch_saida = patch('app.routers.cardapios._saida_produto_organizacao', return_value={'ok': True})
        self.patch_auth.start()
        self.patch_saida.start()
        self.addCleanup(self.patch_auth.stop)
        self.addCleanup(self.patch_saida.stop)

    def test_foto_nao_altera_dados(self):
        alterar_foto_produto(1, 2, FotoProdutoIn(urlfotoproduto='/nova.png'), payload={}, db=self.db)
        self.assertEqual(self.produto.urlfotoproduto, '/nova.png')
        self.assertEqual((self.produto.nmproduto, self.produto.vrprecopadrao, self.produto.sitproduto, self.produto.skuproduto),
                         ('Água', Decimal('5'), 'ATIVO', 'SKU'))
        self.db.commit.assert_called_once()

    def test_dados_nao_alteram_foto_nem_sku(self):
        dados = DadosProdutoIn(nmproduto='Suco', dsproduto=None, vrprecopadrao=7, sitproduto='INATIVO')
        alterar_dados_produto(1, 2, dados, payload={}, db=self.db)
        self.assertEqual(self.produto.nmproduto, 'Suco')
        self.assertEqual(self.produto.urlfotoproduto, '/foto-antiga.png')
        self.assertEqual(self.produto.skuproduto, 'SKU')

    def test_produto_nao_encontrado_nao_salva(self):
        self.db.query.return_value.filter.return_value.first.return_value = None
        with self.assertRaises(HTTPException) as erro:
            alterar_foto_produto(1, 2, FotoProdutoIn(urlfotoproduto='/nova.png'), payload={}, db=self.db)
        self.assertEqual(erro.exception.status_code, 404)
        self.db.commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
