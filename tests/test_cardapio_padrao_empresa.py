import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from fastapi.exceptions import HTTPException
from pydantic import ValidationError

from app.routers.cardapios import ItemPadraoIn, _categoria_do_padrao, _categoria_produto_padrao, _preco_final_item, _saida_item_padrao, _validar_edicao_padrao, criar
from main import app


class CardapioPadraoEmpresaTest(unittest.TestCase):
    def test_itens_exigem_preco_nao_negativo(self):
        item = ItemPadraoIn(cardapiomodelocategoria_id=1, nmproduto="Água", vrprecoprod=0)
        self.assertEqual(item.vrprecoprod, 0)
        self.assertFalse(item.atualizar_preco_lojas)
        with self.assertRaises(ValidationError):
            ItemPadraoIn(cardapiomodelocategoria_id=1, nmproduto="Água", vrprecoprod=-1)
        with self.assertRaises(ValidationError):
            ItemPadraoIn(cardapiomodelocategoria_id=0, nmproduto="Água", vrprecoprod=5)

    def test_desconto_e_cashback_sao_validados(self):
        with self.assertRaises(ValidationError):
            ItemPadraoIn(cardapiomodelocategoria_id=1, nmproduto="Água", vrprecoprod=5, tipodesconto="PERCENTUAL", vrdesconto=101)
        with self.assertRaises(ValidationError):
            ItemPadraoIn(cardapiomodelocategoria_id=1, nmproduto="Água", vrprecoprod=5, pccashback=101)
        with self.assertRaises(ValidationError):
            ItemPadraoIn(cardapiomodelocategoria_id=1, nmproduto="Água", vrprecoprod=5, tipodesconto="VALOR", vrdesconto=6)

    def test_resposta_contem_atributos_do_produto(self):
        vinculo = SimpleNamespace(cardapiomodeloproduto_id=9)
        categoria = SimpleNamespace(cardapiomodelocategoria_id=1, categoria_id=2)
        origem = SimpleNamespace(nmcategoria="Bebidas")
        produto = SimpleNamespace(
            produto_id=3, organizacao_id=4, nmproduto="Água", dsproduto="Sem gás",
            vrprecoprod=12.50, sitproduto="ATIVO", skuproduto="AGUA-01",
            urlfotoproduto="/uploads/agua.jpg", tipodesconto="PERCENTUAL",
            vrdesconto=10, pccashback=5, dtinidesconto=None, dtfimdesconto=None,
            dtcriacao=None, dtultatu=None,
        )
        resposta = _saida_item_padrao(vinculo, produto, categoria, origem)
        self.assertEqual(resposta["categoria_id"], 2)
        self.assertEqual(resposta["produto_id"], 3)
        self.assertEqual(resposta["skuproduto"], "AGUA-01")
        self.assertEqual(resposta["tipodesconto"], "PERCENTUAL")
        self.assertEqual(resposta["pccashback"], 5)
        self.assertIn("dtcriacao", resposta)
        self.assertIn("dtultatu", resposta)

    def test_categoria_precisa_pertencer_a_organizacao(self):
        from unittest.mock import Mock

        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with self.assertRaises(HTTPException) as erro:
            _categoria_produto_padrao(db, 1, 99)
        self.assertEqual(erro.exception.status_code, 422)

    def test_categoria_precisa_pertencer_ao_cardapio(self):
        from unittest.mock import Mock

        db = Mock()
        db.query.return_value.filter.return_value.first.return_value = None
        with self.assertRaises(HTTPException) as erro:
            _categoria_do_padrao(db, 1, 4, 99)
        self.assertEqual(erro.exception.status_code, 404)

    def test_desconto_do_padrao_afeta_preco_final_na_vigencia(self):
        agora = datetime(2026, 9, 16, 12, 0)
        produto = SimpleNamespace(
            tipodesconto="PERCENTUAL", vrdesconto=Decimal("10"),
            dtinidesconto=agora - timedelta(days=1),
            dtfimdesconto=agora + timedelta(days=1),
        )
        preco, ativo = _preco_final_item(Decimal("50.00"), produto, agora)
        self.assertEqual(preco, Decimal("45.00"))
        self.assertTrue(ativo)
        produto.dtinidesconto = agora + timedelta(days=1)
        preco, ativo = _preco_final_item(Decimal("50.00"), produto, agora)
        self.assertEqual(preco, Decimal("50.00"))
        self.assertFalse(ativo)

    def test_loja_nao_cria_cardapio_padrao(self):
        from unittest.mock import patch

        with patch("app.routers.cardapios._loja"):
            with self.assertRaises(HTTPException) as erro:
                criar(1, None, {}, None)
        self.assertEqual(erro.exception.status_code, 403)

    def test_somente_admin_da_empresa_edita_padrao(self):
        payload = {"role": "usuario", "organizacao_id": 7, "loja_id": None, "dscargo": "MANAGER"}
        with self.assertRaises(HTTPException):
            _validar_edicao_padrao(payload, 7)
        payload["dscargo"] = "ADMIN"
        _validar_edicao_padrao(payload, 7)

    def test_fluxo_antigo_nao_esta_publicado(self):
        rotas = {route.path for route in app.routes}
        self.assertIn("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/itens", rotas)
        self.assertNotIn("/organizacoes/{organizacao_id}/cardapio-padrao/copiar-da-loja/{loja_id}", rotas)


if __name__ == "__main__":
    unittest.main()
