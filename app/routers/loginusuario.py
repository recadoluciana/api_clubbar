from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.models.usuario import Usuario
from app.security import verificar_senha, criar_jwt
from app.schemas.auth_usuario import LoginUsuarioIn, LoginUsuarioOut

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/loginusuario", response_model=LoginUsuarioOut)
def loginusuario(payload: LoginUsuarioIn, db: Session = Depends(get_db)):
    try:
        email = payload.emailuser.lower().strip()

        user = (
            db.query(Usuario)
            .filter(
                Usuario.organizacao_id == payload.organizacao_id,
                Usuario.emailuser == email,
                Usuario.situsuario == "ATIVO",
            )
            .first()
        )
    except OperationalError:
        # evita virar 502 quando o MySQL cair
        raise HTTPException(status_code=503, detail="Banco de dados indisponível. Tente novamente.")

    if not user:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    if not verificar_senha(payload.senha, user.senhahashuser):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    token = criar_jwt(
        {
            "sub": str(user.usuario_id),
            "tipo": "usuario",
            "organizacao_id": int(user.organizacao_id),
            "loja_id": int(user.loja_id) if user.loja_id else None,
            "dscargo": user.dscargo,
        }
    )

    # Retorno com NOMES IGUAIS AO BANCO
    return LoginUsuarioOut(
        access_token=token,
        usuario_id=int(user.usuario_id),
        organizacao_id=int(user.organizacao_id),
        loja_id=int(user.loja_id) if user.loja_id else None,
        nmusuario=user.nmusuario,
        emailuser=user.emailuser,
        dscargo=user.dscargo,
        situsuario=user.situsuario,
    )
