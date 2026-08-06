from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from passlib.exc import UnknownHashError
from sqlalchemy.orm import Session
from app.core.security import criar_jwt, verificar_senha
from app.database import get_db
from app.models.operador import Operador
from app.schemas.operador import OperadorLoginIn

router = APIRouter(prefix="/operadores", tags=["Operadores Clubbar"])


@router.post("/login")
def login(payload: OperadorLoginIn, db: Session = Depends(get_db)):
    op = db.query(Operador).filter(Operador.emailoperador == payload.email.lower().strip()).first()
    if not op:
        raise HTTPException(401, "E-mail ou senha invalidos")
    if op.sitoperador != "ATIVO":
        raise HTTPException(403, "Operador inativo")
    try:
        ok = verificar_senha(payload.senha, op.senhahashoperador)
    except UnknownHashError:
        ok = False
    if not ok:
        raise HTTPException(401, "E-mail ou senha invalidos")
    token = criar_jwt({"sub": str(op.operador_id), "role": "operador", "perfil": op.perfil}, timedelta(days=7))
    return {"access_token": token, "token_type": "bearer", "operador_id": op.operador_id,
            "nmoperador": op.nmoperador, "emailoperador": op.emailoperador, "perfil": op.perfil}
