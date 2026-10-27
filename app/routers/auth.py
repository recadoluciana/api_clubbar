import logging
import os

import jwt
from fastapi import APIRouter, HTTPException, Depends
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import get_db

from datetime import datetime, timedelta
from secrets import randbelow

from app.models.cliente import Cliente
from app.models.clienteidentidadesocial import ClienteIdentidadeSocial
from app.models.usuario import Usuario
from app.models.usuariosenha import UsuarioSenha
from app.models.organizacao import Organizacao
from app.schemas.auth import (
    ClienteRegister, ClienteLogin, ClienteLoginSocial, ClientePublic, UserLogin,
    EsqueciSenhaUsuarioRequest, RedefinirSenhaUsuarioRequest,
)
from app.core.security import hash_senha, verificar_senha, criar_jwt, get_usuario_logado
from app.services.email_service import enviar_email_codigo

from passlib.exc import UnknownHashError

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

_APPLE_ISSUER = 'https://appleid.apple.com'
_APPLE_KEYS = jwt.PyJWKClient('https://appleid.apple.com/auth/keys')


def _valores_de_ambiente(nome: str) -> list[str]:
    return [valor.strip() for valor in os.getenv(nome, '').split(',') if valor.strip()]


@router.get('/social-config')
def obter_configuracao_social():
    """Expõe somente a configuração pública necessária ao login social web."""
    client_ids = _valores_de_ambiente('GOOGLE_OAUTH_CLIENT_IDS')
    return {'google_client_id': client_ids[0] if client_ids else ''}


def _validar_google(id_token: str) -> tuple[str, str]:
    client_ids = _valores_de_ambiente('GOOGLE_OAUTH_CLIENT_IDS')
    if not client_ids:
        raise HTTPException(status_code=503, detail='Login com Google não configurado.')

    try:
        dados = google_id_token.verify_oauth2_token(
            id_token,
            google_requests.Request(),
            audience=client_ids,
        )
        if dados.get('iss') not in {'accounts.google.com', 'https://accounts.google.com'}:
            raise ValueError('Emissor Google inválido.')
        if dados.get('email_verified') is not True:
            raise ValueError('E-mail Google não confirmado.')
        subject = str(dados['sub'])
        email = str(dados['email']).lower().strip()
        return subject, email
    except HTTPException:
        raise
    except Exception as erro:
        logger.warning('Token Google recusado: %s', erro)
        raise HTTPException(status_code=401, detail='Não foi possível validar a conta Google.')


def _validar_apple(id_token: str) -> tuple[str, str | None]:
    service_ids = _valores_de_ambiente('APPLE_SERVICE_IDS')
    if not service_ids:
        raise HTTPException(status_code=503, detail='Login com Apple não configurado.')

    try:
        chave = _APPLE_KEYS.get_signing_key_from_jwt(id_token)
        dados = jwt.decode(
            id_token,
            chave.key,
            algorithms=['RS256'],
            audience=service_ids,
            issuer=_APPLE_ISSUER,
            options={'require': ['exp', 'iat', 'sub']},
        )
        email = dados.get('email')
        email_confirmado = dados.get('email_verified')
        if email and email_confirmado not in (True, 'true'):
            raise ValueError('E-mail Apple não confirmado.')
        return str(dados['sub']), str(email).lower().strip() if email else None
    except HTTPException:
        raise
    except Exception as erro:
        logger.warning('Token Apple recusado: %s', erro)
        raise HTTPException(status_code=401, detail='Não foi possível validar a conta Apple.')


def _resposta_login_cliente(cli: Cliente) -> dict:
    token = criar_jwt(
        {'sub': str(cli.cliente_id), 'role': 'cliente'},
        expires_delta=timedelta(days=1000),
    )
    return {
        'access_token': token,
        'token_type': 'bearer',
        'cliente': {
            'cliente_id': cli.cliente_id,
            'nmcliente': cli.nmcliente,
            'emailcliente': cli.emailcliente,
            'emailconf': cli.emailconf,
        },
    }


def _cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or len(set(cpf)) == 1:
        return False

    for tamanho in (9, 10):
        soma = sum(
            int(cpf[indice]) * (tamanho + 1 - indice)
            for indice in range(tamanho)
        )
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[tamanho]):
            return False

    return True

@router.post("/register_cliente")
def register_cliente(data: ClienteRegister, db: Session = Depends(get_db)):
    email = data.emailcliente.lower().strip()

    existe = db.query(Cliente).filter(Cliente.emailcliente == email).first()
    if existe:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    telefone = (data.nrtelcliente or "").strip()

    cpf = ''.join(filter(str.isdigit, data.nrcpfcliente or ""))

    if not _cpf_valido(cpf):
        raise HTTPException(status_code=422, detail="Informe um CPF válido.")

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

    endereco = (data.endcliente or "").strip()
    numero = (data.nrendcliente or "").strip()
    bairro = (data.bairrocliente or "").strip()
    cidade = (data.cidadecliente or "").strip()
    uf = (data.ufcliente or "").strip().upper()
    cep = ''.join(filter(str.isdigit, data.cepcliente or ""))
    endereco_informado = any((endereco, numero, bairro, cidade, uf, cep))

    if endereco_informado and (
        not all((endereco, numero, bairro, cidade))
        or len(uf) != 2
        or len(cep) != 8
    ):
        raise HTTPException(
            status_code=422,
            detail="Informe o endereço completo ou deixe todos os campos de endereço em branco.",
        )

    cli = Cliente(
        nmcliente=(data.nmcliente or "").strip(),
        emailcliente=email,
        senhahashcli=hash_senha(data.senhahashcli),
        nrtelcliente=telefone or None,
        nrcpfcliente=cpf,
        endcliente=endereco or None,
        nrendcliente=numero or None,
        complcliente=(data.complcliente or "").strip() or None,
        bairrocliente=bairro or None,
        cepcliente=cep or None,
        cidadecliente=cidade or None,
        ufcliente=uf or None,
    )

    db.add(cli)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.query(Cliente).filter(Cliente.nrcpfcliente == cpf).first():
            raise HTTPException(
                status_code=400,
                detail="Já existe um cliente cadastrado com este CPF.",
            )
        raise HTTPException(
            status_code=400,
            detail="Já existe um cliente cadastrado com estes dados.",
        )
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
        raise HTTPException(
            status_code=404,
            detail="E-mail digitado não encontrado. Verifique o e-mail informado.",
        )

    if cli.sitcliente != "ATIVO":
        raise HTTPException(status_code=403, detail="Cliente inativo")

    if not verificar_senha(data.senha, cli.senhahashcli):
        raise HTTPException(
            status_code=401,
            detail="Senha não está correta. Verifique e tente novamente.",
        )

    return _resposta_login_cliente(cli)


@router.post('/login-social')
def login_social(data: ClienteLoginSocial, db: Session = Depends(get_db)):
    """Autentica um cliente já cadastrado por uma identidade social validada."""
    if data.provedor == 'google':
        subject, email = _validar_google(data.id_token)
    else:
        subject, email = _validar_apple(data.id_token)

    identidade = (
        db.query(ClienteIdentidadeSocial)
        .filter(
            ClienteIdentidadeSocial.provedor == data.provedor,
            ClienteIdentidadeSocial.subject == subject,
        )
        .first()
    )

    if identidade:
        cli = db.query(Cliente).filter(Cliente.cliente_id == identidade.cliente_id).first()
        if not cli:
            raise HTTPException(status_code=401, detail='Conta social sem cliente vinculado.')
    else:
        if not email:
            raise HTTPException(
                status_code=409,
                detail=(
                    'A Apple não forneceu um e-mail para localizar o cadastro. '
                    'Use a conta Apple que compartilha o e-mail já cadastrado no Clubbar '
                    'ou entre com e-mail e senha.'
                ),
            )
        cli = db.query(Cliente).filter(Cliente.emailcliente == email).first()
        if not cli:
            raise HTTPException(
                status_code=404,
                detail='Este e-mail ainda não possui cadastro no Clubbar. Cadastre-se ou entre com e-mail e senha.',
            )
        identidade = ClienteIdentidadeSocial(
            cliente_id=cli.cliente_id,
            provedor=data.provedor,
            subject=subject,
            email=email,
        )
        db.add(identidade)
        cli.emailconf = 'S'
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=409, detail='Esta conta social já está vinculada a outro cliente.')

    if cli.sitcliente != 'ATIVO':
        raise HTTPException(status_code=403, detail='Cliente inativo')

    return _resposta_login_cliente(cli)


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
