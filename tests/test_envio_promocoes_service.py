import os
import unittest
from unittest.mock import Mock, patch

from app.services.envio_promocoes_service import CanalIndisponivel, enviar_whatsapp_promocional


class EnvioWhatsAppTest(unittest.TestCase):
    @patch.dict(os.environ, {}, clear=True)
    def test_falha_sem_configuracao_sem_fazer_requisicao(self):
        with patch('app.services.envio_promocoes_service.requests.post') as post:
            with self.assertRaises(CanalIndisponivel):
                enviar_whatsapp_promocional(telefone='35999990000', mensagem='Oferta')
            post.assert_not_called()

    @patch.dict(os.environ, {'WHATSAPP_PHONE_NUMBER_ID': '123', 'WHATSAPP_ACCESS_TOKEN': 'teste', 'WHATSAPP_PROMO_TEMPLATE': 'promocao', 'WHATSAPP_GRAPH_VERSION': 'v22.0'}, clear=True)
    def test_numero_brasileiro_e_modelo_aprovado(self):
        resposta = Mock(ok=True)
        resposta.json.return_value = {'messages': [{'id': 'wamid.123'}]}
        with patch('app.services.envio_promocoes_service.requests.post', return_value=resposta) as post:
            self.assertEqual(enviar_whatsapp_promocional(telefone='(35) 99999-0000', mensagem='Oferta'), 'wamid.123')
        corpo = post.call_args.kwargs['json']
        self.assertEqual(corpo['to'], '5535999990000')
        self.assertEqual(corpo['type'], 'template')
        self.assertEqual(corpo['template']['components'][0]['parameters'][0]['text'], 'Oferta')
