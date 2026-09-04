from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.cliente import Cliente
from app.schemas.cliente import AlterarSenhaClienteRequest, ClientePerfilUpdate
from app.core.security import get_usuario_logado, verificar_senha, hash_senha

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.put("/me/alterar_senha")
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
        raise HTTPException(
            status_code=400,
            detail="A senha atual informada está incorreta. Verifique e tente novamente.",
        )

    if payload.senha_atual == payload.nova_senha:
        raise HTTPException(
            status_code=400,
            detail="A nova senha deve ser diferente da senha atual.",
        )

    if len(payload.nova_senha) < 6:
        raise HTTPException(
            status_code=400,
            detail="A nova senha deve conter pelo menos 6 caracteres.",
        )
        
    cliente.senhahashcli = hash_senha(payload.nova_senha)

    db.commit()

    return {"message": "Senha alterada com sucesso"}


@router.get("/me")
def perfil_cliente(
    usuario=Depends(get_usuario_logado),
    db: Session = Depends(get_db)
):
    role = usuario.get("role")
    sub = usuario.get("sub")

    if role != "cliente":
        raise HTTPException(status_code=403, detail="Acesso permitido apenas para cliente")

    cliente_id = int(sub)

    cli = db.query(Cliente).filter(Cliente.cliente_id == cliente_id).first()
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente não cadastrado")

    if cli.sitcliente != "ATIVO":
        raise HTTPException(status_code=403, detail="Cliente inativo")

    return {
        "cliente_id": cli.cliente_id,
        "nmcliente": cli.nmcliente,
        "emailcliente": cli.emailcliente,
        "nrtelcliente": cli.nrtelcliente,
        "nrcpfcliente": cli.nrcpfcliente,
        "endcliente": cli.endcliente,
        "nrendcliente": cli.nrendcliente,
        "complcliente": cli.complcliente,
        "bairrocliente": cli.bairrocliente,
        "cepcliente": cli.cepcliente,
        "cidadecliente": cli.cidadecliente,
        "ufcliente": cli.ufcliente,
        "idcidadeibge": cli.idcidadeibge,
    }


@router.put("/me")
def atualizar_perfil_cliente(
    payload: ClientePerfilUpdate,
    usuario=Depends(get_usuario_logado),
    db: Session = Depends(get_db)
):
    role = usuario.get("role")
    sub = usuario.get("sub")

    if role != "cliente":
        raise HTTPException(status_code=403, detail="Acesso permitido apenas para cliente")

    cliente_id = int(sub)

    cli = db.query(Cliente).filter(Cliente.cliente_id == cliente_id).first()
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente não cadastrado")

    if cli.sitcliente != "ATIVO":
        raise HTTPException(status_code=403, detail="Cliente inativo")

    cpf = ''.join(filter(str.isdigit, payload.nrcpfcliente or '')) or None
    telefone = ''.join(filter(str.isdigit, payload.nrtelcliente or '')) or None
    cep = ''.join(filter(str.isdigit, payload.cepcliente or '')) or None

    if cpf:
        outro = db.query(Cliente).filter(
            Cliente.nrcpfcliente == cpf,
            Cliente.cliente_id != cliente_id
        ).first()

        if outro:
            raise HTTPException(
                status_code=400,
                detail="Já existe outro cliente com este CPF"
            )

    cli.nmcliente = payload.nmcliente.strip()
    cli.nrtelcliente = telefone
    cli.nrcpfcliente = cpf
    cli.endcliente = payload.endcliente.strip() if payload.endcliente else None
    cli.nrendcliente = payload.nrendcliente.strip() if payload.nrendcliente else None
    cli.complcliente = payload.complcliente.strip() if payload.complcliente else None
    cli.bairrocliente = payload.bairrocliente.strip() if payload.bairrocliente else None
    cli.cepcliente = cep
    cli.cidadecliente = payload.cidadecliente.strip() if payload.cidadecliente else None
    cli.ufcliente = payload.ufcliente.strip().upper() if payload.ufcliente else None
    cli.idcidadeibge = payload.idcidadeibge

    db.commit()

    return {
        "message": "Dados atualizados com sucesso",
        "cliente_id": cli.cliente_id,
        "nmcliente": cli.nmcliente,
        "emailcliente": cli.emailcliente,
        "nrtelcliente": cli.nrtelcliente,
        "nrcpfcliente": cli.nrcpfcliente,
        "endcliente": cli.endcliente,
        "nrendcliente": cli.nrendcliente,
        "complcliente": cli.complcliente,
        "bairrocliente": cli.bairrocliente,
        "cepcliente": cli.cepcliente,
        "cidadecliente": cli.cidadecliente,
        "ufcliente": cli.ufcliente,
        "idcidadeibge": cli.idcidadeibge,
    }
