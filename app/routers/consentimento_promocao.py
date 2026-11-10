from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cliente import Cliente


router = APIRouter(prefix="/clientes/me/preferencias-notificacao", tags=["Preferências de notificações"])


class PreferenciasPromocao(BaseModel):
    push: bool = True
    email: bool = True


def _cliente(usuario: dict, db: Session) -> Cliente:
    if usuario.get("role") != "cliente":
        raise HTTPException(403, "Acesso permitido apenas para cliente")
    try:
        cliente_id = int(usuario.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(401, "Sessão inválida")
    cliente = db.query(Cliente).filter(Cliente.cliente_id == cliente_id, Cliente.sitcliente == "ATIVO").first()
    if not cliente:
        raise HTTPException(404, "Cliente não encontrado")
    return cliente


@router.get("")
def consultar(usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    cliente = _cliente(usuario, db)
    return {"push": bool(cliente.recebe_push_promocoes), "email": bool(cliente.recebe_email_promocoes)}


@router.put("")
def atualizar(dados: PreferenciasPromocao, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    cliente = _cliente(usuario, db)
    cliente.recebe_push_promocoes = dados.push
    cliente.recebe_email_promocoes = dados.email
    db.commit()
    return {"push": cliente.recebe_push_promocoes, "email": cliente.recebe_email_promocoes}
