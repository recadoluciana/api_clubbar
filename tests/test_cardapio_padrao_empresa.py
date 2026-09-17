import unittest

from fastapi.exceptions import HTTPException
from pydantic import ValidationError

from app.routers.cardapios import ItemPadraoIn, PrecoPadraoIn, _validar_edicao_padrao, criar
from main import app


class CardapioPadraoEmpresaTest(unittest.TestCase):
    def test_itens_exigem_preco_nao_negativo(self):
        with self.assertRaises(ValidationError):
            ItemPadraoIn(nmcategoria="Bebidas", nmproduto="Água", vrpreco=-1)
        with self.assertRaises(ValidationError):
            PrecoPadraoIn(vrpreco=-1)

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
