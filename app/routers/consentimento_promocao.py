from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cliente import Cliente
from app.models.consentimento_promocao import ConsentimentoPromocao
from app.models.loja import Loja


router = APIRouter(prefix="/clientes/me/promocoes", tags=["Preferências de promoções"])


class PreferenciasPromocao(BaseModel):
    push: bool = False
    whatsapp: bool = False


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


@router.get("/{loja_id}")
def consultar(loja_id: int, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    cliente = _cliente(usuario, db)
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(404, "Estabelecimento não encontrado")
    registro = db.query(ConsentimentoPromocao).filter_by(cliente_id=cliente.cliente_id, loja_id=loja_id).first()
    return {"loja_id": loja_id, "push": bool(registro and registro.push), "whatsapp": bool(registro and registro.whatsapp)}


@router.put("/{loja_id}")
def atualizar(loja_id: int, dados: PreferenciasPromocao, usuario=Depends(get_usuario_logado), db: Session = Depends(get_db)):
    cliente = _cliente(usuario, db)
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(404, "Estabelecimento não encontrado")
    registro = db.query(ConsentimentoPromocao).filter_by(cliente_id=cliente.cliente_id, loja_id=loja_id).first()
    if registro is None:
        registro = ConsentimentoPromocao(cliente_id=cliente.cliente_id, loja_id=loja_id)
        db.add(registro)
    registro.push = dados.push
    registro.whatsapp = dados.whatsapp
    try:
        db.commit()
    except IntegrityError:
        # Requisições simultâneas podem tentar criar a mesma preferência.
        db.rollback()
        registro = db.query(ConsentimentoPromocao).filter_by(
            cliente_id=cliente.cliente_id, loja_id=loja_id
        ).first()
        if registro is None:
            raise
        registro.push = dados.push
        registro.whatsapp = dados.whatsapp
        db.commit()
    return {"loja_id": loja_id, "push": registro.push, "whatsapp": registro.whatsapp}
