import os
import smtplib
from email.mime.text import MIMEText


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


def enviar_email_codigo(destinatario: str, codigo: str):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        raise Exception("SMTP não configurado")

    assunto = "Clubbar - Código de recuperação"

    corpo = f"""
Olá!

Seu código para redefinir sua senha é:

{codigo}

Este código expira em 15 minutos.

Se você não solicitou, ignore este e-mail.
"""

    msg = MIMEText(corpo, "plain", "utf-8")
    msg["Subject"] = assunto
    msg["From"] = SMTP_FROM
    msg["To"] = destinatario

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as server:
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)