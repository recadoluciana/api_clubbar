import unittest
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException

from app.routers.contratolead import (
    IsencaoImplantacaoIn,
    _registrar_isencao_implantacao,
)


class _Query:
    def __init__(self, resultado):
        self.resultado = resultado

    def filter(self, *args):
        return self

    def with_for_update(self):
        return self

    def first(self):
        return self.resultado


class _Db:
    def __init__(self, resultado=None):
        self.resultado = resultado
        self.adicionado = None
        self.commits = 0

    def query(self, _modelo):
        return _Query(self.resultado)

    def add(self, item):
        self.adicionado = item

    def commit(self):
        self.commits += 1

    def refresh(self, _item):
        pass


class IsencaoImplantacaoTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.contrato = SimpleNamespace(
            leadestabelecimentocontrato_id=12,
            leadestabelecimento_id=34,
            vrimplantacao=Decimal("250.00"),
        )
        self.dados = IsencaoImplantacaoIn(
            justificativa="Isenção comercial autorizada"
        )
        self.operador = {"sub": "7"}

    async def test_isenta_sem_gerar_checkout(self):
        db = _Db()

        cobranca = await _registrar_isencao_implantacao(
            db, self.contrato, self.dados, self.operador
        )

        self.assertIs(cobranca, db.adicionado)
        self.assertEqual(cobranca.status, "ISENTA")
        self.assertIsNone(cobranca.asaas_checkout_id)
        self.assertEqual(cobranca.valor, Decimal("250.00"))
        self.assertEqual(cobranca.operadorisencao_id, 7)
        self.assertEqual(db.commits, 1)

    async def test_cancela_checkout_pendente_antes_de_isentar(self):
        cobranca = SimpleNamespace(
            status="PENDENTE",
            asaas_checkout_id="checkout-123",
            justificativaisencao=None,
            operadorisencao_id=None,
            dtisencao=None,
        )
        db = _Db(cobranca)

        with (
            patch(
                "app.routers.contratolead.reconciliar_cobranca_implantacao",
                new=AsyncMock(return_value=cobranca),
            ),
            patch(
                "app.routers.contratolead.cancelar_checkout_asaas",
                new=AsyncMock(),
            ) as cancelar,
            patch("app.routers.contratolead.ASAAS_API_KEY", "api-key"),
        ):
            await _registrar_isencao_implantacao(
                db, self.contrato, self.dados, self.operador
            )

        cancelar.assert_awaited_once_with("checkout-123", "api-key")
        self.assertEqual(cobranca.status, "ISENTA")

    async def test_nao_isenta_implantacao_paga(self):
        cobranca = SimpleNamespace(status="PAGA", asaas_checkout_id="checkout-123")
        db = _Db(cobranca)

        with patch(
            "app.routers.contratolead.reconciliar_cobranca_implantacao",
            new=AsyncMock(return_value=cobranca),
        ):
            with self.assertRaises(HTTPException) as erro:
                await _registrar_isencao_implantacao(
                    db, self.contrato, self.dados, self.operador
                )

        self.assertEqual(erro.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
