import os
from urllib.parse import quote_plus

from dotenv import load_dotenv

load_dotenv()


# Primeiro tenta usar a URL completa fornecida pelo Railway
DATABASE_URL = os.getenv("DATABASE_URL")

# Se não existir, monta a URL com as variáveis usadas localmente
if not DATABASE_URL:
    mysql_host = os.getenv("MYSQL_HOST")
    mysql_port = os.getenv("MYSQL_PORT", "3306")
    mysql_user = os.getenv("MYSQL_USER")
    mysql_password = os.getenv("MYSQL_PASSWORD")
    mysql_db = os.getenv("MYSQL_DB")

    if all([mysql_host, mysql_user, mysql_password, mysql_db]):
        DATABASE_URL = (
            f"mysql+pymysql://"
            f"{quote_plus(mysql_user)}:"
            f"{quote_plus(mysql_password)}@"
            f"{mysql_host}:{mysql_port}/"
            f"{quote_plus(mysql_db)}"
        )


JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "10080"))


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )
)

UPLOAD_DIR = os.getenv(
    "UPLOAD_DIR",
    os.path.join(BASE_DIR, "uploads"),
)

UPLOAD_PRODUTOS = os.path.join(UPLOAD_DIR, "produtos")
UPLOAD_LOJAS = os.path.join(UPLOAD_DIR, "lojas")
UPLOAD_EVENTOS = os.path.join(UPLOAD_DIR, "eventos")

os.makedirs(UPLOAD_PRODUTOS, exist_ok=True)
os.makedirs(UPLOAD_LOJAS, exist_ok=True)
os.makedirs(UPLOAD_EVENTOS, exist_ok=True)
