import unittest
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from app.routers.painel_gerencial import painel_gerencial


class QueryFalsa:
    def __init__(self, resultado, filtros):
        self.resultado = resultado
        self.filtros = filtros

    def filter(self, *criterios):
        self.filtros.extend(str(criterio) for criterio in criterios)
        return self

    def join(self, *args, **kwargs):
        return self

    def select_from(self, *args):
        return self

    def group_by(self, *args):
        return self

    def order_by(self, *args):
        return self

    def all(self):
        return self.resultado

    def one(self):
        return self.resultado

    def scalar(self):
        return self.resultado


class BancoFalso:
    def __init__(self, resultados):
        self.resultados = iter(resultados)
        self.filtros_por_query = []

    def query(self, *args):
        filtros = []
        self.filtros_por_query.append(filtros)
        return QueryFalsa(next(self.resultados), filtros)


class PainelGerencialTest(unittest.TestCase):
    @patch("app.routers.painel_gerencial._hoje_local")
    def test_admin_recebe_dados_reais_agregados_da_organizacao(self, hoje_local):
        hoje_local.return_value = date(2026, 8, 4)
        banco = BancoFalso([
            [
                SimpleNamespace(loja_id=1, nmloja="Loja A"),
                SimpleNamespace(loja_id=2, nmloja="Loja B"),
            ],
            3,
            SimpleNamespace(produtos=Decimal("95.00"), ingressos=Decimal("200.00")),
            Decimal("115.00"),
            4,
            [
                SimpleNamespace(loja_id=1, valor=Decimal("220.00")),
                SimpleNamespace(loja_id=2, valor=Decimal("75.00")),
            ],
            [
                SimpleNamespace(
                    produto_id=10,
                    nome="Cerveja",
                    quantidade=5,
                    valor=Decimal("95.00"),
                )
            ],
            [
                SimpleNamespace(
                    lote_id=20,
                    nmtituloevento="Festival",
                    nmlote="Lote 1",
                    quantidade=4,
                    valor=Decimal("200.00"),
                )
            ],
        ])
        usuario = {
            "sub": "7",
            "role": "usuario",
            "dscargo": "ADMIN",
            "organizacao_id": 9,
            "loja_id": None,
        }

        dados = painel_gerencial(db=banco, usuario=usuario)

        self.assertEqual({"inicio": date(2026, 8, 1), "fim": date(2026, 8, 4)}, dados["periodo"])
        self.assertEqual(115.0, dados["total_hoje"])
        self.assertEqual(295.0, dados["total_mes"])
        self.assertEqual(95.0, dados["total_produtos_mes"])
        self.assertEqual(200.0, dados["total_ingressos_mes"])
        self.assertEqual(
            dados["total_mes"],
            dados["total_produtos_mes"] + dados["total_ingressos_mes"],
        )
        self.assertEqual(3, dados["pedidos_mes"])
        self.assertEqual(4, dados["ingressos_vendidos_mes"])
        self.assertEqual(74.58, dados["participacao_lojas"][0]["percentual"])
        self.assertEqual("Cerveja", dados["produtos_mais_vendidos"][0]["nome"])
        self.assertEqual("Festival - Lote 1", dados["ingressos_mais_vendidos"][0]["nome"])
        filtros = " ".join(filtro for query in banco.filtros_por_query for filtro in query)
        self.assertIn("venda.organizacao_id", filtros)
        self.assertIn("venda.sitvenda", filtros)

    @patch("app.routers.painel_gerencial._hoje_local")
    def test_gerente_fica_limitado_a_loja_do_jwt(self, hoje_local):
        hoje_local.return_value = date(2026, 8, 4)
        banco = BancoFalso([
            [SimpleNamespace(loja_id=4, nmloja="Loja Gerenciada")],
            0,
            SimpleNamespace(produtos=Decimal("0"), ingressos=Decimal("0")),
            Decimal("0"),
            0,
            [],
            [],
            [],
        ])
        usuario = {
            "sub": "8",
            "role": "usuario",
            "dscargo": "GERENTE",
            "organizacao_id": 9,
            "loja_id": 4,
        }

        dados = painel_gerencial(db=banco, usuario=usuario)

        self.assertEqual(4, dados["participacao_lojas"][0]["loja_id"])
        filtros = " ".join(filtro for query in banco.filtros_por_query for filtro in query)
        self.assertIn("loja.loja_id", filtros)
        self.assertIn("venda.loja_id", filtros)
        self.assertIn("produto.loja_id", filtros)
        self.assertIn("eventolote.loja_id", filtros)

    def test_cargo_sem_loja_no_jwt_recebe_403(self):
        banco = BancoFalso([])
        usuario = {
            "sub": "8",
            "role": "usuario",
            "dscargo": "GERENTE",
            "organizacao_id": 9,
            "loja_id": None,
        }

        with self.assertRaises(HTTPException) as erro:
            painel_gerencial(db=banco, usuario=usuario)

        self.assertEqual(403, erro.exception.status_code)
        self.assertEqual("Token sem loja_id válido", erro.exception.detail)
        self.assertEqual([], banco.filtros_por_query)

    def test_token_de_cliente_nao_acessa_painel(self):
        banco = BancoFalso([])
        with self.assertRaises(HTTPException) as erro:
            painel_gerencial(db=banco, usuario={"sub": "10", "role": "cliente"})

        self.assertEqual(403, erro.exception.status_code)
        self.assertEqual([], banco.filtros_por_query)


if __name__ == "__main__":
    unittest.main()
