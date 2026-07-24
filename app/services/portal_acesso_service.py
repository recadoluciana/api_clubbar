#portal_acesso_service.py
import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.leadacesso import LeadAcesso
from app.models.leadparceiro import LeadParceiro


_bearer = HTTPBearer(auto_error=False)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def criar_acesso_portal(
    db: Session,
    *,
    leadparceiro_id: int,
    validade_dias: int = 30,
) -> str:
    token = secrets.token_urlsafe(48)

    db.query(LeadAcesso).filter(
        LeadAcesso.leadparceiro_id == leadparceiro_id,
        LeadAcesso.revogado == "N",
    ).update(
        {"revogado": "S"},
        synchronize_session=False,
    )

    acesso = LeadAcesso(
        leadparceiro_id=leadparceiro_id,
        tokenhash=_hash_token(token),
        dtvalidade=datetime.now() + timedelta(days=validade_dias),
        revogado="N",
    )

    db.add(acesso)
    db.flush()

    return token


def obter_lead_portal(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> LeadParceiro:
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso ao portal não informado.",
        )

    agora = datetime.now()
    tokenhash = _hash_token(credenciais.credentials)

    resultado = (
        db.query(LeadAcesso, LeadParceiro)
        .join(
            LeadParceiro,
            LeadParceiro.leadparceiro_id == LeadAcesso.leadparceiro_id,
        )
        .filter(
            LeadAcesso.tokenhash == tokenhash,
            LeadAcesso.revogado == "N",
            LeadAcesso.dtvalidade >= agora,
        )
        .first()
    )

    if resultado is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Acesso inválido, expirado ou revogado.",
        )

    acesso, lead = resultado
    acesso.dtultimoacesso = agora
    db.commit()

    return lead