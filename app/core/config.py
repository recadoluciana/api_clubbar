import os
from pathlib import Path
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

UPLOAD_DIR = Path(
    os.getenv("UPLOAD_DIR")
    or os.getenv("RAILWAY_VOLUME_MOUNT_PATH")
    or Path(BASE_DIR) / "uploads"
).expanduser().resolve()

UPLOAD_PRODUTOS = UPLOAD_DIR / "produtos"
UPLOAD_LOJAS = UPLOAD_DIR / "lojas"
UPLOAD_EVENTOS = UPLOAD_DIR / "eventos"

UPLOAD_PRODUTOS.mkdir(parents=True, exist_ok=True)
UPLOAD_LOJAS.mkdir(parents=True, exist_ok=True)
UPLOAD_EVENTOS.mkdir(parents=True, exist_ok=True)
