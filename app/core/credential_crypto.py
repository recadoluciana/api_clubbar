import hashlib

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException

from app.core.config import ASAAS_CREDENTIAL_ENCRYPTION_KEY


def _fernet() -> Fernet:
    if not ASAAS_CREDENTIAL_ENCRYPTION_KEY:
        raise HTTPException(status_code=503, detail="ASAAS_CREDENTIAL_ENCRYPTION_KEY não configurada")
    try:
        return Fernet(ASAAS_CREDENTIAL_ENCRYPTION_KEY.encode())
    except (TypeError, ValueError) as erro:
        raise HTTPException(status_code=503, detail="ASAAS_CREDENTIAL_ENCRYPTION_KEY inválida") from erro


def criptografar_credencial(valor: str) -> str:
    return _fernet().encrypt(valor.encode()).decode()


def descriptografar_credencial(valor: str) -> str:
    try:
        return _fernet().decrypt(valor.encode()).decode()
    except InvalidToken as erro:
        raise HTTPException(status_code=503, detail="Não foi possível descriptografar a credencial Asaas") from erro


def hash_token_webhook(valor: str) -> str:
    return hashlib.sha256(valor.encode()).hexdigest()
