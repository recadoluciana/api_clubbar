from datetime import datetime, timedelta
from random import randint

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.models.clisenha import CliSenha

from fastapi import HTTPException
from passlib.context import CryptContext

from app.services.email_service import enviar_email_codigo

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.post("/esqueci-senha")
def esqueci_senha(payload: dict, db: Session = Depends(get_db)):
    email = payload.get("emailcliente")

    cliente = db.query(Cliente).filter(
        Cliente.emailcliente == email
    ).first()

    if not cliente:
        raise HTTPException(
            status_code=404,
            detail="Não existe cliente cadastrado com este e-mail."
        )

    codigo = f"{randint(0, 999999):06d}"
    expiracao = datetime.now() + timedelta(minutes=15)

    # invalida códigos antigos
    db.query(CliSenha).filter(
        CliSenha.cliente_id == cliente.cliente_id,
        CliSenha.usado == "N"
    ).update({"usado": "S"}, synchronize_session=False)

    novo = CliSenha(
        cliente_id=cliente.cliente_id,
        codigo=codigo,
        expiracao=expiracao,
        usado="N",
        dtcriacao=datetime.now(),
    )

    db.add(novo)
    db.commit()

    # 🔥 TEMPORÁRIO (sem email ainda)
    enviar_email_codigo(cliente.emailcliente, codigo)

    return {"message": "Se o e-mail estiver cadastrado, enviaremos um código de recuperação."}


@router.post("/redefinir-senha")
def redefinir_senha(payload: dict, db: Session = Depends(get_db)):
    email = payload.get("emailcliente")
    codigo = payload.get("codigo")
    novasenha = payload.get("novasenha")

    cliente = db.query(Cliente).filter(
        Cliente.emailcliente == email
    ).first()

    if not cliente:
        raise HTTPException(status_code=400, detail="Código inválido")

    registro = db.query(CliSenha).filter(
        CliSenha.cliente_id == cliente.cliente_id,
        CliSenha.codigo == codigo,
        CliSenha.usado == "N"
    ).order_by(CliSenha.clisenha_id.desc()).first()

    if not registro:
        raise HTTPException(status_code=400, detail="Código inválido")

    if registro.expiracao < datetime.now():
        raise HTTPException(status_code=400, detail="Código expirado")

    # 🔐 atualiza senha
    cliente.senhahashcli = pwd_context.hash(novasenha)

    registro.usado = "S"

    db.commit()

    return {"message": "Senha redefinida com sucesso"}