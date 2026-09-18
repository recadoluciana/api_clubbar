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
            "cep": "30130000",
            "endereco": "Rua da Bahia",
            "numero": "100",
            "bairro": "Centro",
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

    def test_aceita_cep_com_mascara_e_normaliza(self):
        item = self._estabelecimento("Bar", 1)
        item["cep"] = "30130-000"
        cadastro = LeadParceiroCreate(nmorganizacao="Grupo Teste", nmresponsavel="Pessoa Teste", telefone="11999999999", email="pessoa@example.com", estabelecimentos=[item])
        self.assertEqual(cadastro.estabelecimentos[0].cep, "30130000")

    def test_empresa_e_endereco_obrigatorios(self):
        item = self._estabelecimento("Bar", 1)
        dados = dict(nmresponsavel="Pessoa Teste", telefone="11999999999", email="pessoa@example.com", estabelecimentos=[item])
        for valor in (None, "", "   "):
            with self.assertRaises(ValidationError):
                LeadParceiroCreate(**dados, nmorganizacao=valor)
        with self.assertRaises(ValidationError):
            LeadParceiroCreate(**dados)
        cadastro = LeadParceiroCreate(**dados, nmorganizacao=" Empresa ")
        self.assertEqual(cadastro.nmorganizacao, "Empresa")
        for campo in ("cep", "endereco", "numero", "bairro", "estado_id", "cidade_id"):
            sem_campo = self._estabelecimento("Bar", 1)
            sem_campo.pop(campo)
            with self.subTest(campo=campo), self.assertRaises(ValidationError):
                LeadParceiroCreate(**{**dados, "estabelecimentos": [sem_campo]}, nmorganizacao="Empresa")
        com_cep_invalido = self._estabelecimento("Bar", 1)
        com_cep_invalido["cep"] = "12345"
        with self.assertRaises(ValidationError):
            LeadParceiroCreate(**{**dados, "estabelecimentos": [com_cep_invalido]}, nmorganizacao="Empresa")


if __name__ == "__main__":
    unittest.main()
