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
        nmcliente=data.nome.strip(),
        emailcliente=email,
        senhahashcli=hash_senha(data.senha),
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
    return {"access_token": token,
            "cliente_id": cli.cliente_id,
            "nmcliente": cli.nmcliente}
