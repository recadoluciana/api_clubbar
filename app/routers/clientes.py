from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.schemas.cliente import AlterarSenhaClienteRequest
from app.core.security import get_usuario_logado, verificar_senha, hash_senha

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.put("/me/senha")
def alterar_minha_senha(
    payload: AlterarSenhaClienteRequest,
    usuario_logado: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    try:
        cliente_id = int(usuario_logado["sub"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Token inválido")

    cliente = (
        db.query(Cliente)
        .filter(Cliente.cliente_id == cliente_id)
        .first()
    )

    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    if not verificar_senha(payload.senha_atual, cliente.senhahashcli):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")

    if payload.senha_atual == payload.nova_senha:
        raise HTTPException(
            status_code=400,
            detail="A nova senha deve ser diferente da senha atual",
        )

    cliente.senhahashcli = hash_senha(payload.nova_senha)

    db.commit()

    return {"message": "Senha alterada com sucesso"}