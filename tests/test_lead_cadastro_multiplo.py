import unittest

from pydantic import ValidationError

from app.schemas.leadparceiro import LeadParceiroCreate


class LeadCadastroMultiploTest(unittest.TestCase):
    def _estabelecimento(self, nome: str, cidade_id: int) -> dict:
        return {
            "nmestabelecimento": nome,
            "tipo": "BAR",
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


if __name__ == "__main__":
    unittest.main()
