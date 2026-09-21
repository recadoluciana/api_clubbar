import unittest

from app.services.cora_ai_service import _texto_da_resposta


class CoraAiTest(unittest.TestCase):
    def test_extrai_texto_estruturado_da_resposta(self):
        dados = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": '{"resposta":"Olá!","encaminhar_atendimento":false}',
                        }
                    ],
                }
            ]
        }
        self.assertEqual(
            '{"resposta":"Olá!","encaminhar_atendimento":false}',
            _texto_da_resposta(dados),
        )

    def test_ignora_saida_sem_texto(self):
        self.assertEqual("", _texto_da_resposta({"output": []}))


if __name__ == "__main__":
    unittest.main()
