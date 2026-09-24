import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.security import criar_jwt
from app.database import get_db
from app.routers.pagamentos import router as pagamentos_router
from app.routers.reservas_ingressos import router as reservas_router


class AutorizacaoPagamentosTest(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(pagamentos_router)
        app.include_router(reservas_router)
        self.db = MagicMock()
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.cliente = {"Authorization": "Bearer " + criar_jwt({"sub": "42", "role": "cliente"})}
        self.outro_cliente = {"Authorization": "Bearer " + criar_jwt({"sub": "99", "role": "cliente"})}
        self.parceiro = {"Authorization": "Bearer " + criar_jwt({"sub": "42", "role": "usuario"})}

    def tearDown(self):
        self.client.close()

    def test_criar_pagamento_exige_token_do_dono_do_carrinho(self):
        corpo = {"cliente_id": 42, "organizacao_id": 1, "loja_id": 2}
        for caminho in ("/pagamentos/pix", "/pagamentos/pagar-asaas"):
            for headers in ({}, self.outro_cliente, self.parceiro):
                self.assertEqual(403, self.client.post(caminho, json=corpo, headers=headers).status_code)
            with patch("app.routers.pagamentos.get_carrinho", return_value=None), patch(
                "app.routers.pagamentos.validar_publicacao_loja"
            ):
                self.assertEqual(404, self.client.post(caminho, json=corpo, headers=self.cliente).status_code)
            for origem in ({"usuario_id": 7}, {"origem_checkout": "PARTNER"}):
                self.assertEqual(
                    403,
                    self.client.post(caminho, json={**corpo, **origem}, headers=self.cliente).status_code,
                )

    def test_reserva_e_status_exigem_token_do_cliente(self):
        corpo = {"cliente_id": 42, "lote_id": 1, "lotepreco_id": 2, "quantidade": 1}
        for headers in ({}, self.outro_cliente, self.parceiro):
            self.assertEqual(403, self.client.post("/reservas-ingressos", json=corpo, headers=headers).status_code)
            self.assertEqual(403, self.client.post("/reservas-ingressos/8/pix", json={"cliente_id": 42}, headers=headers).status_code)
            self.assertEqual(403, self.client.get("/reservas-ingressos/8/status?cliente_id=42", headers=headers).status_code)
        with patch("app.routers.reservas_ingressos.criar_reserva") as criar:
            criar.return_value = SimpleNamespace(
                reserva_ingresso_id=8, organizacao_id=1, loja_id=2, cliente_id=42,
                evento_id=3, lote_id=1, lotepreco_id=2, tipobeneficio=None,
                qtreservada=1, vrunitario=10, pctaxa=0, vrtaxa=0,
                vrtotal=10, sitreserva="PREENCHENDO", dtexpiracao=None, venda_id=None,
            )
            self.assertEqual(200, self.client.post("/reservas-ingressos", json=corpo, headers=self.cliente).status_code)

    def test_status_checkout_nao_expoe_compra_de_outro_cliente(self):
        self.db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(cliente_id=42)
        for headers in ({}, self.outro_cliente, self.parceiro):
            self.assertEqual(403, self.client.get("/pagamentos/asaas/status/pay_123", headers=headers).status_code)


if __name__ == "__main__":
    unittest.main()
