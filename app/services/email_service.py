import os
import smtplib
import socket
from email.mime.text import MIMEText


def enviar_email_codigo(destinatario: str, codigo: str):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    print("SMTP_HOST =", smtp_host)
    print("SMTP_PORT =", smtp_port)
    print("SMTP_USER =", smtp_user)
    print("SMTP_PASSWORD =", "OK" if smtp_password else "VAZIO")
    print("SMTP_FROM =", smtp_from)

    if not smtp_host or not smtp_user or not smtp_password:
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
    msg["From"] = smtp_from
    msg["To"] = destinatario

    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=20) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    except (smtplib.SMTPException, socket.error, OSError) as e:
        print("ERRO SMTP REAL:", repr(e))
        raise Exception(f"Erro ao enviar e-mail: {e}")