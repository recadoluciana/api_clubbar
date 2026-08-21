from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db

from datetime import datetime, timedelta
from secrets import randbelow

from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.models.usuariosenha import UsuarioSenha
from app.models.organizacao import Organizacao
from app.schemas.auth import (
    ClienteRegister, ClienteLogin, ClientePublic, UserLogin,
    EsqueciSenhaUsuarioRequest, RedefinirSenhaUsuarioRequest,
)
from app.core.security import hash_senha, verificar_senha, criar_jwt, get_usuario_logado
from app.services.email_service import enviar_email_codigo

from passlib.exc import UnknownHashError

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register_cliente")
def register_cliente(data: ClienteRegister, db: Session = Depends(get_db)):
    email = data.emailcliente.lower().strip()

    existe = db.query(Cliente).filter(Cliente.emailcliente == email).first()
    if existe:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    telefone = (data.nrtelcliente or "").strip()

    cpf = ''.join(filter(str.isdigit, data.nrcpfcliente or ""))

    if cpf:
        cliente_existente = (
            db.query(Cliente)
            .filter(Cliente.nrcpfcliente == cpf)
            .first()
        )

        if cliente_existente:
            raise HTTPException(
                status_code=400,
                detail="Já existe um cliente cadastrado com este CPF."
            )

    cli = Cliente(
        nmcliente=(data.nmcliente or "").strip(),
        emailcliente=email,
        senhahashcli=hash_senha(data.senhahashcli),
        nrtelcliente=telefone or None,
        nrcpfcliente=cpf or None,
    )

    db.add(cli)
    db.commit()
    db.refresh(cli)

    token = criar_jwt(
        {"sub": str(cli.cliente_id), "role": "cliente"},
        expires_delta=timedelta(days=1000),
    )

    return {
        "access_token": token,
        "cliente": {
            "cliente_id": cli.cliente_id,
            "nmcliente": cli.nmcliente,
            "emailcliente": cli.emailcliente,
            "emailconf": cli.emailconf,
        },
    }

@router.post("/login")
def login(data: ClienteLogin, db: Session = Depends(get_db)):

    email = data.email.lower().strip()

    cli = db.query(Cliente).filter(Cliente.emailcliente == email).first()
    if not cli:
        raise HTTPException(status_code=401,detail="E-mail ou senha inválidos",)

    if cli.sitcliente != "ATIVO":
        raise HTTPException(status_code=403, detail="Cliente inativo")

    if not verificar_senha(data.senha, cli.senhahashcli):
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

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
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    user, nmorganizacao = row

    if user.situsuario != "ATIVO":
        raise HTTPException(status_code=403, detail="Usuário inativo")

    try:
        ok = verificar_senha(data.senha, user.senhahashuser)
    except UnknownHashError:
        raise HTTPException(
            status_code=401,
            detail="E-mail ou senha inválidos",
        )

    if not ok:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")

    token = criar_jwt(
        {
            "sub": str(user.usuario_id),
            "role": "usuario",
            "dscargo": user.dscargo,
            "organizacao_id": user.organizacao_id,
            "loja_id": user.loja_id,
        },
        expires_delta=timedelta(days=1000),
    )

    return {
        "access_token": token,
        "token_type": "bearer",

        "usuario_id": user.usuario_id,
        "nmusuario": user.nmusuario,
        "emailuser": user.emailuser,

        "loja_id": user.loja_id,
        "organizacao_id": user.organizacao_id,
        "nmorganizacao": nmorganizacao or "",

        "dscargo": user.dscargo,
    }

@router.post("/esqueci-senha-user")
def esqueci_senha_usuario(
    data: EsqueciSenhaUsuarioRequest,
    db: Session = Depends(get_db),
):
    email = data.email.lower().strip()
    usuario = db.query(Usuario).filter(Usuario.emailuser == email).first()
    mensagem = (
        "Se o e-mail estiver cadastrado, enviaremos um código de recuperação. "
        "Verifique também sua caixa de spam."
    )
    if not usuario:
        return {"message": mensagem}

    codigo = f"{randbelow(1_000_000):06d}"
    agora = datetime.now()
    db.query(UsuarioSenha).filter(
        UsuarioSenha.usuario_id == usuario.usuario_id,
        UsuarioSenha.usado == "N",
    ).update({"usado": "S"}, synchronize_session=False)
    db.add(UsuarioSenha(
        usuario_id=usuario.usuario_id,
        codigohash=hash_senha(codigo),
        expiracao=agora + timedelta(minutes=15),
        usado="N",
        dtcriacao=agora,
    ))
    db.flush()
    try:
        enviar_email_codigo(usuario.emailuser, codigo)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"message": mensagem}


@router.post("/redefinir-senha-user")
def redefinir_senha_usuario(
    data: RedefinirSenhaUsuarioRequest,
    db: Session = Depends(get_db),
):
    email = data.email.lower().strip()
    usuario = db.query(Usuario).filter(Usuario.emailuser == email).first()
    if not usuario:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    registros = db.query(UsuarioSenha).filter(
        UsuarioSenha.usuario_id == usuario.usuario_id,
        UsuarioSenha.usado == "N",
    ).order_by(UsuarioSenha.usuariosenha_id.desc()).limit(5).all()
    agora = datetime.now()
    registro_valido = next((registro for registro in registros
        if registro.expiracao >= agora and verificar_senha(data.codigo, registro.codigohash)
    ), None)
    if registro_valido is None:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    usuario.senhahashuser = hash_senha(data.nova_senha)
    registro_valido.usado = "S"
    db.query(UsuarioSenha).filter(
        UsuarioSenha.usuario_id == usuario.usuario_id,
        UsuarioSenha.usado == "N",
    ).update({"usado": "S"}, synchronize_session=False)
    db.commit()
    return {"message": "Senha redefinida com sucesso."}

@router.get("/debug/hora")
def debug_hora():
    from datetime import datetime
    from zoneinfo import ZoneInfo

    return {
        "server_now": str(datetime.now()),
        "br_now": str(datetime.now(ZoneInfo("America/Sao_Paulo"))),
    }
