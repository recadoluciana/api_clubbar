import unittest

from pydantic import ValidationError

from app.schemas.leadparceiro import LeadParceiroCreate


class LeadCadastroMultiploTest(unittest.TestCase):
    def _estabelecimento(self, nome: str, cidade_id: int) -> dict:
        return {
            "nmestabelecimento": nome,
            "tipo": "BAR",
            "cpfcnpj": "52998224725",
            "tipovenda": "AMBOS",
            "estado_id": 17,
            "cidade_id": cidade_id,
        }

    def test_aceita_varios_estabelecimentos_no_mesmo_cadastro(self):
        payload = LeadParceiroCreate(
            nmresponsavel="Luciana Binatto",
            nmorganizacao="Grupo Binatto",
            telefone="35999999999",
            email="luciana@example.com",
            estabelecimentos=[
                self._estabelecimento("Adega Bar", 1),
                self._estabelecimento("Club 35", 2),
            ],
        )
        self.assertEqual(2, len(payload.estabelecimentos))
        self.assertEqual("Grupo Binatto", payload.nmorganizacao)

    def test_exige_ao_menos_um_estabelecimento(self):
        with self.assertRaises(ValidationError):
            LeadParceiroCreate(
                nmresponsavel="Luciana Binatto",
                telefone="35999999999",
                email="luciana@example.com",
                estabelecimentos=[],
            )

    def test_exige_documento_em_cada_estabelecimento(self):
        for documento in (None, "", "123", "123456789012", "somente letras"):
            with self.subTest(documento=documento), self.assertRaises(ValidationError):
                item = self._estabelecimento("Bar", 1)
                item["cpfcnpj"] = documento
                LeadParceiroCreate(nmorganizacao="Grupo Teste", nmresponsavel="Pessoa Teste", telefone="11999999999", email="pessoa@example.com", estabelecimentos=[item])
        item.pop("cpfcnpj")
        with self.assertRaises(ValidationError):
            LeadParceiroCreate(nmorganizacao="Grupo Teste", nmresponsavel="Pessoa Teste", telefone="11999999999", email="pessoa@example.com", estabelecimentos=[item])

    def test_aceita_cpf_ou_cnpj_com_mascara(self):
        for documento, esperado in [("529.982.247-25", "52998224725"), ("11.222.333/0001-81", "11222333000181")]:
            item = self._estabelecimento("Bar", 1)
            item["cpfcnpj"] = documento
            cadastro = LeadParceiroCreate(nmorganizacao="Grupo Teste", nmresponsavel="Pessoa Teste", telefone="11999999999", email="pessoa@example.com", estabelecimentos=[item])
            self.assertEqual(cadastro.estabelecimentos[0].cpfcnpj, esperado)

    def test_empresa_obrigatoria_e_endereco_opcional(self):
        item = self._estabelecimento("Bar", 1)
        item.pop("estado_id")
        item.pop("cidade_id")
        dados = dict(nmresponsavel="Pessoa Teste", telefone="11999999999", email="pessoa@example.com", estabelecimentos=[item])
        for valor in (None, "", "   "):
            with self.assertRaises(ValidationError):
                LeadParceiroCreate(**dados, nmorganizacao=valor)
        with self.assertRaises(ValidationError):
            LeadParceiroCreate(**dados)
        cadastro = LeadParceiroCreate(**dados, nmorganizacao=" Empresa ")
        self.assertEqual(cadastro.nmorganizacao, "Empresa")
        self.assertIsNone(cadastro.estabelecimentos[0].estado_id)
        self.assertIsNone(cadastro.estabelecimentos[0].cidade_id)


if __name__ == "__main__":
    unittest.main()
