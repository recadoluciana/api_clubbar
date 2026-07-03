import os
import httpx
from fastapi import HTTPException


BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL")
BREVO_FROM_NAME = os.getenv("BREVO_FROM_NAME", "Clubbar")


def enviar_email_codigo(destinatario: str, codigo: str):

    if not BREVO_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="BREVO_API_KEY não configurada."
        )

    body = {
        "sender": {
            "name": BREVO_FROM_NAME,
            "email": BREVO_FROM_EMAIL,
        },
        "to": [
            {
                "email": destinatario,
            }
        ],
        "subject": "Recuperação de senha - Clubbar",
        "htmlContent": f"""
        <h2>Recuperação de senha</h2>

        <p>Seu código é:</p>

        <h1 style="letter-spacing:4px;">
            {codigo}
        </h1>

        <p>
            Este código expira em <b>15 minutos</b>.
        </p>

        <p>
            Se você não solicitou esta recuperação,
            ignore este e-mail.
        </p>

        <br>

        <b>Equipe Clubbar</b>
        """
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