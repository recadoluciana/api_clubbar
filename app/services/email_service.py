import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configurações
smtp_server = "smtp.hostinger.com"
port = 465  # SSL
sender_email = "seuemail@seudominio.com"
password = "sua_senha"
receiver_email = "destinatario@exemplo.com"

# Criando mensagem
message = MIMEMultipart("alternative")
message["Subject"] = "Teste de envio via Hostinger"
message["From"] = sender_email
message["To"] = receiver_email

texto = "Este é um teste de envio de e-mail via Hostinger SMTP."
message.attach(MIMEText(texto, "plain"))

# Conexão segura e envio
with smtplib.SMTP_SSL(smtp_server, port) as server:
    server.login(sender_email, password)
    server.sendmail(sender_email, receiver_email, message.as_string())

print("E-mail enviado com sucesso!")