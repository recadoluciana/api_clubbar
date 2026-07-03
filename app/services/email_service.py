import os
import httpx
from fastapi import HTTPException
from app.services.email_templates import template_email_clubbar


BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL")
BREVO_FROM_NAME = os.getenv("BREVO_FROM_NAME", "Clubbar")


def enviar_email_codigo(destinatario: str, codigo: str):
    if not BREVO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="BREVO_API_KEY não configurada.",
        )

    conteudo_html = f"""
    <p style="font-size:16px;color:#444;">
      Utilize o código abaixo para redefinir sua senha:
    </p>

    <div style="
      margin:35px auto;
      background:#FFC107;
      border-radius:10px;
      padding:20px;
      text-align:center;
      font-size:42px;
      font-weight:bold;
      letter-spacing:8px;
      color:#000;
    ">
      {codigo}
    </div>

    <p style="font-size:15px;color:#555;">
      Este código é válido por <b>15 minutos</b>.
    </p>

    <p style="font-size:15px;color:#555;">
      Caso você não tenha solicitado esta recuperação,
      basta ignorar este e-mail.
    </p>
    """

    html = template_email_clubbar(
        titulo="Recuperação de senha",
        subtitulo="Recebemos uma solicitação para redefinir sua senha no Clubbar.",
        conteudo_html=conteudo_html,
        botao_texto="Abrir Clubbar",
        botao_link="https://app.clubbar.com.br",
    )

    body = {
        "sender": {
            "name": BREVO_FROM_NAME,
            "email": BREVO_FROM_EMAIL,
        },
        "to": [{"email": destinatario}],
        "subject": "Recuperação de senha - Clubbar",
        "htmlContent": html,
    }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": BREVO_API_KEY,
    }

    response = httpx.post(
        "https://api.brevo.com/v3/smtp/email",
        json=body,
        headers=headers,
        timeout=30,
    )

    print("[BREVO]", response.status_code)
    print(response.text)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=response.text,
        )