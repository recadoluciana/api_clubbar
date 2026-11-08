"""Adaptadores de envio; o chamador deve selecionar destinatários autorizados.

Os provedores são configurados no servidor. Este módulo nunca registra os
tokens de acesso ou os dados de contato nos logs.
"""
import os
import json
import re

import requests


class CanalIndisponivel(Exception):
    pass


class FalhaEnvio(Exception):
    pass


def verificar_configuracao_push() -> None:
    projeto = os.getenv('FIREBASE_PROJECT_ID', '').strip()
    if not projeto or not re.fullmatch(r'[a-z0-9-]+', projeto):
        raise CanalIndisponivel('Notificações do aplicativo ainda não configuradas.')
    try:
        import google.auth
        from google.oauth2 import service_account
        dados = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON', '').strip()
        if dados:
            credenciais = service_account.Credentials.from_service_account_info(json.loads(dados))
            if credenciais.project_id != projeto:
                raise ValueError('Projeto da credencial não corresponde ao Firebase.')
        else:
            google.auth.default()
    except Exception as exc:
        raise CanalIndisponivel('Credenciais do Firebase ainda não estão configuradas.') from exc


def enviar_whatsapp_promocional(*, telefone: str, mensagem: str) -> str:
    """Envia por um modelo aprovado com uma variável no corpo: {{1}}.

    O número e a aprovação do modelo pertencem à conta WhatsApp Business
    configurada pela Clubbar. O texto é fornecido como parâmetro do modelo.
    """
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    token = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
    template = os.getenv("WHATSAPP_PROMO_TEMPLATE", "").strip()
    versao = os.getenv("WHATSAPP_GRAPH_VERSION", "").strip()
    idioma = os.getenv("WHATSAPP_PROMO_TEMPLATE_LANGUAGE", "pt_BR").strip()
    if not phone_id or not token or not template or not versao:
        raise CanalIndisponivel("WhatsApp Business ainda não configurado.")
    numero = re.sub(r"\D", "", telefone)
    if len(numero) in (10, 11):
        numero = "55" + numero
    if not 12 <= len(numero) <= 15:
        raise FalhaEnvio("Número de telefone inválido.")
    if not re.fullmatch(r"v\d+\.\d+", versao) or not re.fullmatch(r"\d+", phone_id):
        raise CanalIndisponivel("Configuração do WhatsApp Business inválida.")
    mensagem = " ".join(mensagem.split())
    if not mensagem or len(mensagem) > 1024:
        raise FalhaEnvio("A mensagem deve conter entre 1 e 1024 caracteres.")
    payload = {
        "messaging_product": "whatsapp",
        "to": numero,
        "type": "template",
        "template": {
            "name": template,
            "language": {"code": idioma},
            "components": [{"type": "body", "parameters": [{"type": "text", "text": mensagem}]}],
        },
    }
    try:
        resposta = requests.post(
            f"https://graph.facebook.com/{versao}/{phone_id}/messages",
            headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=15,
        )
        if not resposta.ok:
            raise FalhaEnvio("O WhatsApp não aceitou a mensagem.")
        dados = resposta.json()
        mensagens = dados.get("messages") or []
        if not mensagens or not mensagens[0].get("id"):
            raise FalhaEnvio("O WhatsApp não retornou confirmação de envio.")
        return str(mensagens[0]["id"])
    except (requests.RequestException, ValueError) as exc:
        raise FalhaEnvio("Não foi possível confirmar o envio ao WhatsApp.") from exc


def enviar_push_promocional(*, token_dispositivo: str, titulo: str, mensagem: str) -> str:
    projeto = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    if not projeto:
        raise CanalIndisponivel("Notificações do aplicativo ainda não configuradas.")
    if not re.fullmatch(r"[a-z0-9-]+", projeto):
        raise CanalIndisponivel("Configuração do Firebase inválida.")
    try:
        import google.auth
        from google.auth.transport.requests import Request

        escopos = ["https://www.googleapis.com/auth/firebase.messaging"]
        credencial_json = os.getenv('FIREBASE_SERVICE_ACCOUNT_JSON', '').strip()
        if credencial_json:
            from google.oauth2 import service_account
            credenciais = service_account.Credentials.from_service_account_info(json.loads(credencial_json), scopes=escopos)
        else:
            credenciais, _ = google.auth.default(scopes=escopos)
        credenciais.refresh(Request())
        resposta = requests.post(
            f"https://fcm.googleapis.com/v1/projects/{projeto}/messages:send",
            headers={"Authorization": f"Bearer {credenciais.token}"},
            json={"message": {"token": token_dispositivo, "notification": {"title": titulo, "body": mensagem}}},
            timeout=15,
        )
        if not resposta.ok:
            raise FalhaEnvio("O Firebase não aceitou a notificação.")
        identificador = resposta.json().get("name")
        if not identificador:
            raise FalhaEnvio("O Firebase não retornou confirmação de envio.")
        return str(identificador)
    except FalhaEnvio:
        raise
    except Exception as exc:
        raise FalhaEnvio("Não foi possível confirmar o envio da notificação.") from exc
