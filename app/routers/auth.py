from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db

from datetime import datetime, timedelta

from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.organizacao import Organizacao
from app.schemas.auth import ClienteRegister, ClienteLogin, ClientePublic, UserLogin
from app.core.security import hash_senha, verificar_senha, criar_jwt, get_usuario_logado    

from passlib.exc import UnknownHashError

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register_cliente")
def register_cliente(data: ClienteRegister, db: Session = Depends(get_db)):
    email = data.emailcliente.lower().strip()

    existe = db.query(Cliente).filter(Cliente.emailcliente == email).first()
    if existe:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    telefone = (data.nrtelcliente or "").strip()
    cpf = (data.nrcpfcliente or "").strip()

    cli = Cliente(
        nmcliente=(data.nmcliente or "").strip(),
        emailcliente=(data.emailcliente or "").strip().lower(),
        senhahashcli=hash_senha(data.senhahashcli),
        nrtelcliente=telefone or None,
        nrcpfcliente=cpf or None,
    )
    db.add(cli)
    db.commit()
    db.refresh(cli)

    # token já loga após cadastrar (se quiser, dá pra não logar e pedir confirmação de e-mail)
    token = criar_jwt({"sub": str(cli.cliente_id), "role": "cliente"},expires_delta=timedelta(days=1000))
    return {
        "access_token": token,
        "cliente": {
            "cliente_id"  : cli.cliente_id,
            "nmcliente"   : cli.nmcliente,
            "emailcliente": cli.emailcliente,
            "emailconf"   : cli.emailconf,
        }
    }

@router.post("/login")
def login(data: ClienteLogin, db: Session = Depends(get_db)):
    
    email = data.email.lower().strip()

    cli = db.query(Cliente).filter(Cliente.emailcliente == email).first()
    if not cli:
        raise HTTPException(status_code=401, detail="E-mail não cadastrado")

    if cli.sitcliente != "ATIVO":
        raise HTTPException(status_code=403, detail="Cliente inativo")

    if not verificar_senha(data.senha, cli.senhahashcli):
        raise HTTPException(status_code=401, detail="Senha inválida")

    token = criar_jwt({"sub": str(cli.cliente_id), "role": "cliente"},expires_delta=timedelta(days=1000))

    print('retorno um json com access_token, cliente_id, nmcliente', token, cli.cliente_id,cli.nmcliente)

    return {
        "access_token": token,
        "cliente": {
            "cliente_id"  : cli.cliente_id,
            "nmcliente"   : cli.nmcliente,
            "emailcliente": cli.emailcliente,
            "emailconf"   : cli.emailconf,
        }
    }


@router.post("/loginuser")
def loginuser(data: UserLogin, db: Session = Depends(get_db)):
    email = data.email.lower().strip()

    row = (
        db.query(Usuario, Organizacao.nmorganizacao)
        .outerjoin(
            Organizacao,
            Organizacao.organizacao_id == Usuario.organizacao_id,
        )
        .filter(Usuario.emailuser == email)
        .first()
    )

    if not row:
        raise HTTPException(status_code=401, detail="E-mail não cadastrado")

    user, nmorganizacao = row

    if user.situsuario != "ATIVO":
        raise HTTPException(status_code=403, detail="Usuário inativo")

    try:
        ok = verificar_senha(data.senha, user.senhahashuser)
    except UnknownHashError:
        raise HTTPException(
            status_code=401,
            detail="Senha inválida (hash inválido no banco)",
        )

    if not ok:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    token = criar_jwt(
        {"sub": str(user.usuario_id), "role": "usuario"},
        expires_delta=timedelta(days=1000),
    )

    print(
        'retorno um json com access_token, usuario_id, nmusuario',
        token,
        user.usuario_id,
        user.nmusuario,
    )

    return {
        "access_token": token,
        "usuario_id": user.usuario_id,
        "nmusuario": user.nmusuario,
        "loja_id": user.loja_id,
        "organizacao_id": user.organizacao_id,
        "nmorganizacao": nmorganizacao or "",
    }

@router.get("/debug/hora")
def debug_hora():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return {
        "server_now": str(datetime.now()),
        "br_now": str(datetime.now(ZoneInfo("America/Sao_Paulo"))),
    }