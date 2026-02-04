from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.schemas.auth import ClienteRegister, ClienteLogin, ClientePublic
from app.security import hash_senha, verificar_senha, criar_jwt

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
    
    print('entrei na api login ')

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

    return {"access_token": token,
            "cliente_id": cli.cliente_id,
            "nmcliente": cli.nmcliente}


@router.get("/perfil")
def perfil_cliente(cliente_id: int, db: Session = Depends(get_db)):
    
    print('entrei na api pefil cliente ')

    cli = db.query(Cliente).filter(Cliente.cliente_id == cliente_id).first()
    if not cli:
        raise HTTPException(status_code=401, detail="Cliente não cadastrado")

    if cli.sitcliente != "ATIVO":
        raise HTTPException(status_code=403, detail="Cliente inativo")

    return {"cliente_id"    : cli.cliente_id,
            "nmcliente"     : cli.nmcliente,
            "emailcliente"  : cli.emailcliente,
            "nrtelcliente"  : cli.nrtelcliente,
            "nrcpfcliente"  : cli.nrcpfcliente}
