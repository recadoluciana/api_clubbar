import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from fastapi import HTTPException

from app.routers.pagamentos import (
    _calcular_comissao_produtos_mercado_pago,
    _recalcular_itens_carrinho,
)


class PagamentoPrecoCardapioTest(unittest.TestCase):
    def test_comissao_mercado_pago_usa_percentual_da_loja(self):
        self.assertEqual(
            _calcular_comissao_produtos_mercado_pago(5.25, Decimal("5")),
            Decimal("0.26"),
        )

    def _db(self, item):
        produto = SimpleNamespace(
            produto_id=3, organizacao_id=1, nmproduto="Teste", sitproduto="ATIVO",
            vrprecoprod=Decimal("100.00"), tipodesconto="PERCENTUAL",
            vrdesconto=Decimal("10.00"), dtinidesconto=None, dtfimdesconto=None,
        )
        consulta_produto = Mock()
        consulta_produto.filter.return_value.first.return_value = produto
        consulta_item = Mock()
        consulta_item.join.return_value.join.return_value.filter.return_value.first.return_value = item
        db = Mock()
        db.query.side_effect = [consulta_produto, consulta_item]
        return db

    def test_checkout_usa_snapshot_validado_do_carrinho(self):
        db = self._db(SimpleNamespace(vrpreco=Decimal("80.00")))
        itens, total = _recalcular_itens_carrinho(
            db, [{"produto_id": 3, "cardapioitem_id": 7, "vrprecoprod": 80, "qtitcarrinho": 2}], 5, 1,
        )
        self.assertEqual(itens[0]["vrunitario"], 80.0)
        self.assertEqual(total, 160.0)

    def test_checkout_rejeita_produto_de_outra_organizacao(self):
        db = self._db(SimpleNamespace(vrpreco=Decimal("90.00")))
        with self.assertRaises(HTTPException) as erro:
            _recalcular_itens_carrinho(
                db,
                [{"produto_id": 3, "cardapioitem_id": 7, "vrprecoprod": 90, "qtitcarrinho": 1}],
                5,
                2,
            )
        self.assertEqual(erro.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
