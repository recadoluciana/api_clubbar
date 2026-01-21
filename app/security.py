from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
from jose import jwt

from app.config import JWT_SECRET, JWT_EXPIRES_MIN

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)

def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)

def criar_jwt(payload: dict) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=JWT_EXPIRES_MIN)
    data = {**payload, "iat": now, "exp": exp}
    return jwt.encode(data, JWT_SECRET, algorithm="HS256")
