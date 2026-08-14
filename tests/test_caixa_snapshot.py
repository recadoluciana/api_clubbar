import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from app.models.carrinho import Carrinho
from app.models.checkout_asaas import CheckoutAsaas
from app.models.checkout_asaas_item import CheckoutAsaasItem
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda
from app.models.venda import Venda
from app.services.venda_gateway_service import criar_venda_paga_por_checkout_snapshot


class _Query:
    def __init__(self, result):
        self.result = result

    def filter(self, *args):
        return self

    def with_for_update(self):
        return self

    def order_by(self, *args):
        return self

    def first(self):
        return self.result[0] if isinstance(self.result, list) else self.result

    def all(self):
        return self.result if isinstance(self.result, list) else [self.result]


class _Db:
    def __init__(self, checkout, itens, carrinho):
        self.checkout = checkout
        self.itens = itens
        self.carrinho = carrinho
        self.adicionados = []

    def query(self, model):
        if model is CheckoutAsaas:
            return _Query(self.checkout)
        if model is CheckoutAsaasItem:
            return _Query(self.itens)
        if model is Carrinho:
            return _Query(self.carrinho)
        raise AssertionError(f"Consulta inesperada: {model}")

    def add(self, objeto):
        if isinstance(objeto, Venda):
            objeto.venda_id = 101
        if isinstance(objeto, PagVenda):
            objeto.pagvenda_id = 202
        self.adicionados.append(objeto)

    def flush(self):
        pass


class CaixaSnapshotTest(unittest.IsolatedAsyncioTestCase):
    async def test_webhook_cria_venda_itens_e_pagamento_pelo_snapshot(self):
        checkout = SimpleNamespace(
            checkout_asaas_id=7,
            venda_id=None,
            carrinho_id=8,
            loja_id=9,
            cliente_id=10,
            valor=Decimal("25.00"),
            external_reference="PIX-DEV-CAIXA-8-abc",
            checkout_id="qr_123",
            payment_id=None,
        )
        item = SimpleNamespace(
            checkout_asaas_item_id=1,
            produto_id=5,
            lote_id=None,
            quantidade=2,
            vrunitario=Decimal("12.50"),
            dsobsitem=None,
            nmparticipante=None,
            cpfparticipante=None,
            pctaxaitvenda=Decimal("5.00"),
            vrtaxaitvenda=Decimal("0.63"),
        )
        carrinho = SimpleNamespace(organizacao_id=3, usuario_id=4)
        db = _Db(checkout, [item], carrinho)

        with (
            patch(
                "app.services.venda_gateway_service.set_venda_como_paga",
                return_value={"ok": True},
            ) as confirmar,
            patch(
                "app.services.venda_gateway_service.gerar_token_qr",
                side_effect=["token-1", "token-2"],
            ),
        ):
            resultado = await criar_venda_paga_por_checkout_snapshot(
                db,
                checkout_asaas_id=7,
                gateway="ASAAS",
                pagamento={
                    "id": "pay_123",
                    "billingType": "PIX",
                    "status": "RECEIVED",
                },
            )

        self.assertEqual(resultado["venda_id"], 101)
        self.assertEqual(checkout.venda_id, 101)
        self.assertEqual(len([x for x in db.adicionados if isinstance(x, ItVenda)]), 2)
        pagamento = next(x for x in db.adicionados if isinstance(x, PagVenda))
        self.assertEqual(pagamento.dsmetodopag, "PIX")
        confirmar.assert_called_once_with(
            db,
            venda_id=101,
            gateway="ASAAS",
            payload={
                "id": "pay_123",
                "billingType": "PIX",
                "status": "RECEIVED",
            },
            finalizar_carrinho=False,
        )

    async def test_reenvio_reutiliza_venda_ja_associada(self):
        checkout = SimpleNamespace(checkout_asaas_id=7, venda_id=101)
        db = _Db(checkout, [], None)
        resultado = await criar_venda_paga_por_checkout_snapshot(
            db,
            checkout_asaas_id=7,
            gateway="ASAAS",
            pagamento={"id": "pay_123"},
        )
        self.assertTrue(resultado["already_processed"])
        self.assertEqual(db.adicionados, [])


if __name__ == "__main__":
    unittest.main()
