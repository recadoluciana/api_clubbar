import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from pydantic import ValidationError

from app.routers.cardapios import (
    ItemIn,
    ProdutoOrganizacaoIn,
    _preco_final_item,
)
from main import app


class CardapioEmpresaTest(unittest.TestCase):
    def test_item_exige_preco_positivo(self):
        self.assertEqual(ItemIn(produto_id=1, vrpreco=10).sititem, "ATIVO")
        self.assertEqual(
            ItemIn(produto_id=1, vrpreco=10, sititem="INATIVO").sititem,
            "INATIVO",
        )
        with self.assertRaises(ValidationError):
            ItemIn(produto_id=1, vrpreco=0)
        with self.assertRaises(ValidationError):
            ItemIn(produto_id=1, vrpreco=10, sititem="INDISPONIVEL")

    def test_produto_da_empresa_exige_preco_positivo(self):
        self.assertEqual(
            ProdutoOrganizacaoIn(nmproduto="Água", vrprecopadrao=5).vrprecopadrao,
            Decimal("5"),
        )
        with self.assertRaises(ValidationError):
            ProdutoOrganizacaoIn(nmproduto="Água", vrprecopadrao=0)

    def test_desconto_e_cashback_sao_validados(self):
        with self.assertRaises(ValidationError):
            ItemIn(
                produto_id=1,
                vrpreco=5,
                tipodesconto="PERCENTUAL",
                vrdesconto=100,
            )
        with self.assertRaises(ValidationError):
            ItemIn(produto_id=1, vrpreco=5, pccashback=101)
        with self.assertRaises(ValidationError):
            ItemIn(
                produto_id=1,
                vrpreco=5,
                tipodesconto="VALOR",
                vrdesconto=5,
            )

    def test_desconto_afeta_preco_final_na_vigencia(self):
        agora = datetime(2026, 9, 16, 12, 0)
        item = SimpleNamespace(
            vrpreco=Decimal("50.00"),
            tipodesconto="PERCENTUAL",
            vrdesconto=Decimal("10"),
            dtinidesconto=agora - timedelta(days=1),
            dtfimdesconto=agora + timedelta(days=1),
        )
        preco, ativo = _preco_final_item(item, agora)
        self.assertEqual(preco, Decimal("45.00"))
        self.assertTrue(ativo)

        item.dtinidesconto = agora + timedelta(days=1)
        preco, ativo = _preco_final_item(item, agora)
        self.assertEqual(preco, Decimal("50.00"))
        self.assertFalse(ativo)

    def test_rotas_do_cardapio_da_empresa_estao_publicadas(self):
        rotas = {route.path for route in app.routes}
        self.assertIn("/organizacoes/{organizacao_id}/produtos", rotas)
        self.assertIn("/lojas/{loja_id}/cardapio-publicado", rotas)
        self.assertNotIn(
            "/organizacoes/{organizacao_id}/cardapio-padrao/copiar-da-loja/{loja_id}",
            rotas,
        )


if __name__ == "__main__":
    unittest.main()
