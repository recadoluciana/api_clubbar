import traceback
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.organizacao import Organizacao
from app.models.usuario import Usuario

from app.schemas.organizacao import OrganizacaoUpdate

from app.models.cidade import Cidade
from app.models.estado import Estado

router = APIRouter(tags=["Organizacoes"])


@router.get("/organizacoes/usuario/{usuario_id}")
def listar_organizacao_do_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
):
    resultado = (
        db.query(
            Organizacao,
            Cidade.nmcidade,
            Estado.sgestado,
        )
        .join(
            Usuario,
            Usuario.organizacao_id == Organizacao.organizacao_id,
        )
        .outerjoin(
            Cidade,
            Cidade.cidade_id == Organizacao.cidade_id,
        )
        .outerjoin(
            Estado,
            Estado.estado_id == Cidade.estado_id,
        )
        .filter(
            Usuario.usuario_id == usuario_id,
        )
        .first()
    )

    if not resultado:
        raise HTTPException(
            status_code=404,
            detail="Organização não encontrada para este usuário",
        )

    organizacao, nmcidade, sgestado = resultado

    return {
        "organizacao_id": organizacao.organizacao_id,
        "nmorganizacao": organizacao.nmorganizacao,
        "rzsocialorganizacao": organizacao.rzsocialorganizacao,
        "cnpjorganizacao": organizacao.cnpjorganizacao,
        "emailorganizacao": organizacao.emailorganizacao,
        "telorganizacao": organizacao.telorganizacao,
        "ceporganizacao": organizacao.ceporganizacao,
        "endorganizacao": organizacao.endorganizacao,
        "nrendorganizacao": organizacao.nrendorganizacao,
        "complorganizacao": organizacao.complorganizacao,
        "cidade_id": organizacao.cidade_id,
        "nmcidade": nmcidade,
        "sgestado": sgestado,
        "nmbairro": organizacao.nmbairro,
        "leadparceiro_id": organizacao.leadparceiro_id,
        "sitorganizacao": organizacao.sitorganizacao,
        "dtcriacao": organizacao.dtcriacao,
        "dtultatu": organizacao.dtultatu,
    }

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


from sqlalchemy import or_

@router.post("/organizacoes")
def cadastrar_organizacao(
    dados: OrganizacaoCreate,
    db: Session = Depends(get_db),
):
    try:
        # Verifica CNPJ duplicado
        existe = (
            db.query(Organizacao)
            .filter(
                Organizacao.cnpjorganizacao == dados.cnpjorganizacao
            )
            .first()
        )

        if existe:
            raise HTTPException(
                status_code=400,
                detail="Já existe uma organização com este CNPJ.",
            )

        # Verifica e-mail duplicado
        existe = (
            db.query(Organizacao)
            .filter(
                Organizacao.emailorganizacao == dados.emailorganizacao
            )
            .first()
        )

        if existe:
            raise HTTPException(
                status_code=400,
                detail="Já existe uma organização com este e-mail.",
            )

        # Verifica se a cidade existe
        cidade = (
            db.query(Cidade)
            .filter(
                Cidade.cidade_id == dados.cidade_id
            )
            .first()
        )

        if not cidade:
            raise HTTPException(
                status_code=400,
                detail="Cidade inválida.",
            )

        nova = Organizacao(
            nmorganizacao=dados.nmorganizacao,
            rzsocialorganizacao=dados.rzsocialorganizacao,
            cnpjorganizacao=dados.cnpjorganizacao,
            emailorganizacao=dados.emailorganizacao,
            telorganizacao=dados.telorganizacao,
            ceporganizacao=dados.ceporganizacao,
            endorganizacao=dados.endorganizacao,
            nrendorganizacao=dados.nrendorganizacao,
            complorganizacao=dados.complorganizacao,
            cidade_id=dados.cidade_id,
            nmbairro=dados.nmbairro,
            leadparceiro_id=dados.leadparceiro_id,
            sitorganizacao="ATIVA",
        )

        db.add(nova)
        db.commit()
        db.refresh(nova)

        return {
            "mensagem": "Organização cadastrada com sucesso.",
            "organizacao_id": nova.organizacao_id,
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e),
        )