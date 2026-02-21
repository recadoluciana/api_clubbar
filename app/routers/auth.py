from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.models.usuario import Usuario
from app.schemas.auth import ClienteRegister, ClienteLogin, ClientePublic, UserLogin
from app.core.security import hash_senha, verificar_senha, criar_jwt, get_usuario_logado    

from passlib.exc import UnknownHashError

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
def register(data: ClienteRegister, db: Session = Depends(get_db)):
    email = data.email.lower().strip()

    existe = db.query(Cliente).filter(Cliente.emailcliente == email).first()
    if existe:
        raise HTTPException(status_code=400, detail="E-mail já cadastrado")

    cli = Cliente(
        nmcliente     = data.nome.strip(),
        emailcliente  = email,
        senhahashcli  = hash_senha(data.senha),
        nrtelcliente  = data.nrtelcliente.strip(),
        nrcpfcliente  = data.nrcpfcliente.strip(),
        # emailconf fica "N" por padrão
    )
    db.add(cli)
    db.commit()
    db.refresh(cli)

    # token já loga após cadastrar (se quiser, dá pra não logar e pedir confirmação de e-mail)
    token = criar_jwt({"sub": str(cli.cliente_id), "role": "cliente"})
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

    token = criar_jwt({"sub": str(cli.cliente_id), "role": "cliente"})

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


@router.get("/perfil")
def perfil_cliente(
    usuario=Depends(get_usuario_logado),  # 👈 vem do token
    db: Session = Depends(get_db)
):
    role = usuario.get("role")
    sub = usuario.get("sub")

    if role != "cliente":
        raise HTTPException(status_code=403, detail="Acesso permitido apenas para cliente")

    cliente_id = int(sub)

    cli = db.query(Cliente).filter(Cliente.cliente_id == cliente_id).first()
    if not cli:
        raise HTTPException(status_code=401, detail="Cliente não cadastrado")

    if cli.sitcliente != "ATIVO":
        raise HTTPException(status_code=403, detail="Cliente inativo")

    return {
        "cliente_id": cli.cliente_id,
        "nmcliente": cli.nmcliente,
        "emailcliente": cli.emailcliente,
        "nrtelcliente": cli.nrtelcliente,
        "nrcpfcliente": cli.nrcpfcliente,
    }

@router.post("/loginuser")
def loginuser(data: UserLogin, db: Session = Depends(get_db)):
    
    print('entrei na api loginuser')

    email = data.email.lower().strip()

    user = db.query(Usuario).filter(Usuario.emailuser == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="E-mail não cadastrado")

    if user.situsuario != "ATIVO":
        raise HTTPException(status_code=403, detail="Usuário inativo")

    try:
        ok = verificar_senha(data.senha, user.senhahashuser)
    except UnknownHashError:
        raise HTTPException(status_code=401, detail="Senha inválida (hash inválido no banco)")

    if not ok:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos")


    token = criar_jwt({"sub": str(user.usuario_id), "role": "usuario"})

    print('retorno um json com access_token, usuario_id, nmusuario', token, user.usuario_id,user.nmusuario)

    return {"access_token": token,
            "usuario_id": user.usuario_id,
            "nmusuario" : user.nmusuario}






