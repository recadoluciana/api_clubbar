import os
import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def enviar_email_codigo(destinatario: str, codigo: str):
    smtp_server = os.getenv("SMTP_HOST", "smtp.hostinger.com")
    smtp_port = int(os.getenv("SMTP_PORT", "465"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_user or not smtp_password:
        raise Exception("SMTP não configurado.")

    mensagem = MIMEMultipart("alternative")
    mensagem["Subject"] = "Recuperação de senha - Clubbar"
    mensagem["From"] = smtp_from
    mensagem["To"] = destinatario

    texto = f"""
Olá!

Recebemos uma solicitação para redefinir sua senha do Clubbar.

Seu código de recuperação é:

{codigo}

Este código é válido por 15 minutos.

Se você não solicitou esta recuperação, basta ignorar este e-mail.

Equipe Clubbar
"""

    mensagem.attach(MIMEText(texto, "plain", "utf-8"))

    print("=" * 80)
    print("[EMAIL]")
    print("HOST.......:", smtp_server)
    print("PORT.......:", smtp_port)
    print("USER.......:", smtp_user)
    print("DESTINO....:", destinatario)
    print("=" * 80)

    try:
        with smtplib.SMTP_SSL(
            smtp_server,
            smtp_port,
            timeout=30,
        ) as server:

            print("[EMAIL] Conectado.")

            server.login(
                smtp_user,
                smtp_password,
            )

            print("[EMAIL] Login OK.")

            server.sendmail(
                smtp_user,
                destinatario,
                mensagem.as_string(),
            )

            print("[EMAIL] Enviado com sucesso.")

    except Exception as e:
        print("[EMAIL][ERRO]", repr(e))
        raise