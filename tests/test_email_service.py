import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.services.email_service import (
    enviar_confirmacao_cadastro_lead,
    enviar_email_codigo,
)


class RespostaBrevoFalsa:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class EmailServiceTest(unittest.TestCase):
    @patch('app.services.email_service._enviar_email')
    def test_confirmacao_cadastro_inclui_lead_e_estabelecimentos(self, enviar):
        enviar_confirmacao_cadastro_lead(
            'bia@example.com',
            {
                'nmresponsavel': 'Bia Binatto',
                'nmorganizacao': 'Grupo Bia',
                'email': 'bia@example.com',
                'telefone': '35999999999',
            },
            [
                {
                    'nmestabelecimento': 'Bia Bar',
                    'tipo': 'BAR',
                    'tipovenda': 'AMBOS',
                    'cidade': 'Alfenas',
                    'estado': 'MG',
                }
            ],
        )

        destinatario, assunto, html = enviar.call_args.args
        self.assertEqual('bia@example.com', destinatario)
        self.assertIn('Confirmação', assunto)
        self.assertIn('Bia Binatto', html)
        self.assertIn('Grupo Bia', html)
        self.assertIn('Bia Bar', html)
        self.assertIn('Alfenas - MG', html)

    def test_ip_nao_autorizado_retorna_indisponibilidade_sem_expor_brevo(self):
        resposta = RespostaBrevoFalsa(
            401,
            'We have detected you are using an unrecognised IP address',
        )
        with (
            patch('app.services.email_service.BREVO_API_KEY', 'chave'),
            patch('app.services.email_service.BREVO_FROM_EMAIL', 'suporte@clubbar.com.br'),
            patch('app.services.email_service.httpx.post', return_value=resposta),
            self.assertRaises(HTTPException) as erro,
        ):
            enviar_email_codigo('cliente@example.com', '123456')

        self.assertEqual(503, erro.exception.status_code)
        self.assertIn('temporariamente indisponível', erro.exception.detail)
        self.assertNotIn('unrecognised IP', erro.exception.detail)

    def test_erro_generico_do_brevo_retorna_bad_gateway(self):
        resposta = RespostaBrevoFalsa(400, 'invalid_parameter')
        with (
            patch('app.services.email_service.BREVO_API_KEY', 'chave'),
            patch('app.services.email_service.BREVO_FROM_EMAIL', 'suporte@clubbar.com.br'),
            patch('app.services.email_service.httpx.post', return_value=resposta),
            self.assertRaises(HTTPException) as erro,
        ):
            enviar_email_codigo('cliente@example.com', '123456')

        self.assertEqual(502, erro.exception.status_code)
        self.assertNotIn('invalid_parameter', erro.exception.detail)


if __name__ == '__main__':
    unittest.main()

