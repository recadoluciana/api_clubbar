import os
import smtplib
from email.message import EmailMessage


def enviar_email_codigo(destinatario: str, codigo: str):
    smtp_host = os.getenv("SMTP_HOST", "smtp.hostinger.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    print("HOST =", smtp_host)
    print("PORT =", smtp_port)

    if not smtp_user or not smtp_password:
        raise Exception("SMTP não configurado")

    msg = EmailMessage()
    msg["Subject"] = "Código de recuperação de senha - Clubbar"
    msg["From"] = smtp_from
    msg["To"] = destinatario

    msg.set_content(
        f"""
Olá!

Seu código para redefinir a senha no Clubbar é:

{codigo}

Este código expira em 15 minutos.

Se você não solicitou essa recuperação, ignore este e-mail.

Equipe Clubbar
"""
    )

    with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(msg)