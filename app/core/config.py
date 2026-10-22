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

# Percentual legal reservado à meia-entrada. Mantido em configuração para que
# a mesma regra seja usada nos cálculos da API e nas telas dos aplicativos.
PERCENTUAL_COTA_LEGAL = max(
    0.0,
    min(100.0, float(os.getenv("PERCENTUAL_COTA_LEGAL", "40"))),
)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip()
PIXABAY_API_KEY = os.getenv("PIXABAY_API_KEY", "").strip()
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

# Railway Buckets expose these official S3-compatible variable names when
# credentials are attached to a service. Keep the STORAGE_S3_* names as an
# override for local/custom deployments, but use the official names by
# default so the access key, secret, endpoint and bucket come from the same
# Railway credential set.
STORAGE_S3_ENDPOINT = (
    os.getenv("ENDPOINT") or os.getenv("STORAGE_S3_ENDPOINT") or ""
).strip()
STORAGE_S3_ACCESS_KEY_ID = (
    os.getenv("ACCESS_KEY_ID") or os.getenv("STORAGE_S3_ACCESS_KEY_ID") or ""
).strip()
STORAGE_S3_SECRET_ACCESS_KEY = (
    os.getenv("SECRET_ACCESS_KEY")
    or os.getenv("STORAGE_S3_SECRET_ACCESS_KEY")
    or ""
).strip()
STORAGE_S3_BUCKET = (
    os.getenv("BUCKET") or os.getenv("STORAGE_S3_BUCKET") or ""
).strip()
STORAGE_S3_REGION = (
    os.getenv("REGION") or os.getenv("STORAGE_S3_REGION") or "auto"
).strip()
STORAGE_S3_ADDRESSING_STYLE = (
    os.getenv("STORAGE_S3_ADDRESSING_STYLE") or "virtual-host"
).strip()


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
UPLOAD_CAMPANHAS = UPLOAD_DIR / "campanhas"
UPLOAD_MATERIAIS_LEAD = UPLOAD_DIR / "materiais-lead"

# Armazenamento de objetos S3. Em produção, os uploads usam o bucket e a API
# continua expondo as URLs estáveis em /uploads/. Sem estas credenciais, o
# comportamento local baseado em diretório é preservado para desenvolvimento.
STORAGE_S3_ENDPOINT = os.getenv("STORAGE_S3_ENDPOINT", "").strip()
STORAGE_S3_ACCESS_KEY_ID = os.getenv("STORAGE_S3_ACCESS_KEY_ID", "").strip()
STORAGE_S3_SECRET_ACCESS_KEY = os.getenv("STORAGE_S3_SECRET_ACCESS_KEY", "").strip()
STORAGE_S3_BUCKET = os.getenv("STORAGE_S3_BUCKET", "").strip()
STORAGE_S3_REGION = os.getenv("STORAGE_S3_REGION", "auto").strip() or "auto"
STORAGE_S3_ADDRESSING_STYLE = (
    os.getenv("STORAGE_S3_ADDRESSING_STYLE", "virtual").strip() or "virtual"
)

UPLOAD_PRODUTOS.mkdir(parents=True, exist_ok=True)
UPLOAD_LOJAS.mkdir(parents=True, exist_ok=True)
UPLOAD_EVENTOS.mkdir(parents=True, exist_ok=True)
UPLOAD_ATRACOES.mkdir(parents=True, exist_ok=True)
UPLOAD_CAMPANHAS.mkdir(parents=True, exist_ok=True)
UPLOAD_MATERIAIS_LEAD.mkdir(parents=True, exist_ok=True)
