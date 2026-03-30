from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.organizacao import Organizacao
from app.models.usuario import Usuario

from app.schemas.organizacao import OrganizacaoUpdate

router = APIRouter(tags=["Organizacoes"])


@router.get("/organizacoes/usuario/{usuario_id}")
def listar_organizacao_do_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(
        Usuario.usuario_id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    organizacao = db.query(Organizacao).filter(
        Organizacao.organizacao_id == usuario.organizacao_id
    ).first()

    if not organizacao:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    return organizacao

@router.put("/organizacoes/usuario/{usuario_id}")
def atualizar_organizacao_do_usuario(
    usuario_id: int,
    dados: OrganizacaoUpdate,
    db: Session = Depends(get_db)
):
    usuario = db.query(Usuario).filter(
        Usuario.usuario_id == usuario_id
    ).first()

    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")

    organizacao = db.query(Organizacao).filter(
        Organizacao.organizacao_id == usuario.organizacao_id
    ).first()

    if not organizacao:
        raise HTTPException(status_code=404, detail="Organização não encontrada")

    if dados.nmorganizacao is not None:
        organizacao.nmorganizacao = dados.nmorganizacao

    if dados.cnpjorganizacao is not None:
        organizacao.cnpjorganizacao = dados.cnpjorganizacao

    if dados.emailorganizacao is not None:
        organizacao.emailorganizacao = dados.emailorganizacao

    if dados.telorganizacao is not None:
        organizacao.telorganizacao = dados.telorganizacao

    if dados.sitorganizacao is not None:
        organizacao.sitorganizacao = dados.sitorganizacao

    db.commit()
    db.refresh(organizacao)

    return {
        "mensagem": "Organização atualizada com sucesso",
        "organizacao_id": organizacao.organizacao_id
    }

from app.schemas.organizacao import OrganizacaoCreate


@router.post("/organizacoes")
def cadastrar_organizacao(
    dados: OrganizacaoCreate,
    db: Session = Depends(get_db)
):
    try:
        nova = Organizacao(
            nmorganizacao=dados.nmorganizacao,
            cnpjorganizacao=dados.cnpjorganizacao,
            emailorganizacao=dados.emailorganizacao,
            telorganizacao=dados.telorganizacao,
            sitorganizacao="ATIVA"
        )

        db.add(nova)
        db.commit()
        db.refresh(nova)

        return {
            "mensagem": "Organização cadastrada com sucesso",
            "organizacao_id": nova.organizacao_id
        }

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


        