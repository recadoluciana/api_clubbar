import unittest
from unittest.mock import patch

from fastapi import HTTPException

from app.services.email_service import enviar_email_codigo


class RespostaBrevoFalsa:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text


class EmailServiceTest(unittest.TestCase):
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

