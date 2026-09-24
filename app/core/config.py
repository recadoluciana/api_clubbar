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


APP_ENV = os.getenv("APP_ENV", "development").strip().lower()
JWT_SECRET = os.getenv("JWT_SECRET", "").strip()
if APP_ENV in {"production", "prod"} and (
    len(JWT_SECRET) < 32 or JWT_SECRET == "change-me"
):
    raise RuntimeError("JWT_SECRET seguro é obrigatório em produção")
if not JWT_SECRET:
    JWT_SECRET = "change-me"
JWT_EXPIRES_MIN = int(os.getenv("JWT_EXPIRES_MIN", "10080"))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip()
ASAAS_API_KEY = os.getenv("ASAAS_API_KEY", "").strip()
ASAAS_SANDBOX_PAYER_API_KEY = os.getenv("ASAAS_SANDBOX_PAYER_API_KEY", "").strip()
ASAAS_WEBHOOK_TOKEN = os.getenv("ASAAS_WEBHOOK_TOKEN", "").strip()
ASAAS_CREDENTIAL_ENCRYPTION_KEY = os.getenv("ASAAS_CREDENTIAL_ENCRYPTION_KEY", "").strip()
ASAAS_CLUBBAR_WALLET_ID = os.getenv("ASAAS_CLUBBAR_WALLET_ID", "").strip()
ASAAS_PIX_ADDRESS_KEY = os.getenv("ASAAS_PIX_ADDRESS_KEY", "").strip()

_railway_public_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN", "").strip()
PUBLIC_API_BASE_URL = os.getenv("PUBLIC_API_BASE_URL", "").strip().rstrip("/")
if not PUBLIC_API_BASE_URL and _railway_public_domain:
    PUBLIC_API_BASE_URL = f"https://{_railway_public_domain}".rstrip("/")

PUBLIC_CLIENT_BASE_URL = (
    os.getenv("PUBLIC_CLIENT_BASE_URL")
    or os.getenv("APP_BASE_URL")
    or ""
).strip().rstrip("/")

# O serviço do Clubbar Client no Railway foi renomeado. Mantém a aplicação
# compatível com a variável antiga até que todos os ambientes sejam atualizados.
_CLIENT_HOSTS_ANTIGOS = {
    "https://clubbarcliente-desenvolvimento.up.railway.app":
        "https://clubbarclient-desenvolvimento.up.railway.app",
    "https://clubbarcliente-production.up.railway.app":
        "https://clubbarclient-production.up.railway.app",
}
PUBLIC_CLIENT_BASE_URL = _CLIENT_HOSTS_ANTIGOS.get(
    PUBLIC_CLIENT_BASE_URL,
    PUBLIC_CLIENT_BASE_URL,
)

PUBLIC_PARTNER_BASE_URL = (
    os.getenv("PUBLIC_PARTNER_BASE_URL")
    or os.getenv("PARTNER_URL")
    or ""
).strip().rstrip("/")

PUBLIC_SITE_URL = os.getenv("PUBLIC_SITE_URL", "").strip().rstrip("/")


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
UPLOAD_ATRACOES = UPLOAD_DIR / "atracoes"
UPLOAD_MATERIAIS_LEAD = UPLOAD_DIR / "materiais-lead"

UPLOAD_PRODUTOS.mkdir(parents=True, exist_ok=True)
UPLOAD_LOJAS.mkdir(parents=True, exist_ok=True)
UPLOAD_EVENTOS.mkdir(parents=True, exist_ok=True)
UPLOAD_ATRACOES.mkdir(parents=True, exist_ok=True)
UPLOAD_MATERIAIS_LEAD.mkdir(parents=True, exist_ok=True)
