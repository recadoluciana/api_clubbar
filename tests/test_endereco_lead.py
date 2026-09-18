import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException

from app.services.endereco_lead import validar_cep_lead


class EnderecoLeadTest(unittest.TestCase):
    def setUp(self):
        self.cidade = Mock(estado_id=1, cdibgecid=3106200, nmcidade="Belo Horizonte")
        self.estado = Mock(estado_id=1, sgestado="MG")

    @patch("app.services.endereco_lead.httpx.get")
    def test_cep_confere_com_cidade_e_estado(self, get):
        get.return_value.json.return_value = {"cep": "30130-000", "uf": "MG", "ibge": "3106200", "localidade": "Belo Horizonte"}
        validar_cep_lead("30130000", self.cidade, self.estado)
        get.assert_called_once()

    @patch("app.services.endereco_lead.httpx.get")
    def test_rejeita_cep_inexistente_ou_de_outra_cidade(self, get):
        get.return_value.json.return_value = {"erro": True}
        with self.assertRaises(HTTPException) as erro:
            validar_cep_lead("30130000", self.cidade, self.estado)
        self.assertEqual(erro.exception.status_code, 422)
        get.return_value.json.return_value = {"cep": "30130-000", "uf": "MG", "ibge": "3106201", "localidade": "Outra"}
        with self.assertRaises(HTTPException) as erro:
            validar_cep_lead("30130000", self.cidade, self.estado)
        self.assertEqual(erro.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
