# app/core/security.py
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from passlib.context import CryptContext
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from app.core.config import JWT_SECRET, JWT_EXPIRES_MIN

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

bearer_scheme = HTTPBearer(auto_error=False)  # <- não explode sozinho, a gente controla

def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)

def verificar_senha(senha: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha, senha_hash)

def criar_jwt(payload: dict, expires_delta: timedelta | None = None) -> str:
    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(days=7)  # padrão 7 dias

    exp = now + expires_delta

    data = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }

    return jwt.encode(data, JWT_SECRET, algorithm="HS256")


def verificar_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except JWTError:
        raise HTTPException(status_code=402, detail="Token inválido")


def get_usuario_logado(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=403, detail="Não autenticado")

    token = credentials.credentials
    payload = verificar_jwt(token)

    # (opcional, mas eu recomendo) garante que tem "sub"
    if "sub" not in payload:
        raise HTTPException(status_code=404, detail="Token sem 'sub'")

    return payload
