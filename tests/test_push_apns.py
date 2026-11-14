from unittest.mock import Mock

import pytest

from app.services.envio_promocoes_service import enviar_push_promocional


@pytest.mark.parametrize('plataforma', ['ios', 'android'])
def test_envio_usa_parametros_apns_apenas_no_ios(monkeypatch, plataforma):
    import google.auth
    import requests

    monkeypatch.setenv('FIREBASE_PROJECT_ID', 'projeto-teste')
    monkeypatch.delenv('FIREBASE_SERVICE_ACCOUNT_JSON', raising=False)
    credenciais = Mock(token='credencial')
    monkeypatch.setattr(google.auth, 'default', lambda **kwargs: (credenciais, None))
    resposta = Mock(ok=True)
    resposta.json.return_value = {'name': 'mensagem-teste'}
    post = Mock(return_value=resposta)
    monkeypatch.setattr(requests, 'post', post)

    assert enviar_push_promocional(
        token_dispositivo='dispositivo', titulo='Título', mensagem='Mensagem',
        plataforma=plataforma,
    ) == 'mensagem-teste'
    mensagem = post.call_args.kwargs['json']['message']
    if plataforma == 'ios':
        assert mensagem['apns']['headers'] == {
            'apns-push-type': 'alert', 'apns-priority': '10',
            'apns-topic': 'br.com.clubbar.cliente',
        }
        assert mensagem['apns']['payload']['aps']['sound'] == 'default'
    else:
        assert 'apns' not in mensagem
