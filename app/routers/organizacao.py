import traceback
from sqlalchemy import or_
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_usuario_logado
from app.core.permissoes_loja import validar_gerenciamento_organizacao
from app.models.organizacao import Organizacao
from app.models.usuario import Usuario

from app.schemas.organizacao import OrganizacaoUpdate
from app.schemas.organizacao import OrganizacaoCreate

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
            Estado.estado_id == Organizacao.estado_id,
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
        "estado_id": organizacao.estado_id,
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
    usuario_logado: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    usuario = (
        db.query(Usuario)
        .filter(Usuario.usuario_id == usuario_id)
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado",
        )

    organizacao = (
        db.query(Organizacao)
        .filter(
            Organizacao.organizacao_id == usuario.organizacao_id
        )
        .first()
    )

    if not organizacao:
        raise HTTPException(
            status_code=404,
            detail="Organização não encontrada",
        )

    print("===================================")
    print("estado_id recebido:", dados.estado_id)
    print("cidade_id recebido:", dados.cidade_id)
    print("===================================")

    # ----------------------------------------------------
    # Atualiza cidade e estado de forma consistente
    # ----------------------------------------------------
    if dados.cidade_id is not None:

        cidade = (
            db.query(Cidade)
            .filter(Cidade.cidade_id == dados.cidade_id)
            .first()
        )

        if not cidade:
            raise HTTPException(
                status_code=400,
                detail="Cidade inválida.",
            )

        # Se o Flutter enviou estado, valida apenas por segurança
        if (
            dados.estado_id is not None
            and cidade.estado_id != dados.estado_id
        ):
            raise HTTPException(
                status_code=400,
                detail="A cidade selecionada não pertence ao estado informado.",
            )

        print(
            f"Cidade escolhida: {cidade.nmcidade} "
            f"(Estado {cidade.estado_id})"
        )

        # A cidade determina o estado
        organizacao.cidade_id = cidade.cidade_id
        organizacao.estado_id = cidade.estado_id

    elif dados.estado_id is not None:

        estado = (
            db.query(Estado)
            .filter(Estado.estado_id == dados.estado_id)
            .first()
        )

        if not estado:
            raise HTTPException(
                status_code=400,
                detail="Estado inválido.",
            )

        organizacao.estado_id = estado.estado_id

    # ----------------------------------------------------
    # Demais campos
    # ----------------------------------------------------

    if dados.nmorganizacao is not None:
        organizacao.nmorganizacao = dados.nmorganizacao

    if dados.rzsocialorganizacao is not None:
        organizacao.rzsocialorganizacao = dados.rzsocialorganizacao

    if dados.cnpjorganizacao is not None:
        organizacao.cnpjorganizacao = dados.cnpjorganizacao

    if dados.emailorganizacao is not None:
        organizacao.emailorganizacao = dados.emailorganizacao

    if dados.telorganizacao is not None:
        organizacao.telorganizacao = dados.telorganizacao

    if dados.ceporganizacao is not None:
        organizacao.ceporganizacao = dados.ceporganizacao

    if dados.endorganizacao is not None:
        organizacao.endorganizacao = dados.endorganizacao

    if dados.nrendorganizacao is not None:
        organizacao.nrendorganizacao = dados.nrendorganizacao

    if dados.complorganizacao is not None:
        organizacao.complorganizacao = dados.complorganizacao

    if dados.nmbairro is not None:
        organizacao.nmbairro = dados.nmbairro

    try:
        db.commit()
        db.refresh(organizacao)

        return {
            "mensagem": "Organização atualizada com sucesso",
            "organizacao_id": organizacao.organizacao_id,
        }

    except Exception as e:
        db.rollback()
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao atualizar organização: {str(e)}",
        )
        
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
            estado_id=dados.estado_id,
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

    if int(usuario_logado.get("sub") or 0) != usuario_id:
        raise HTTPException(status_code=403, detail="Usuário do login não confere.")
    validar_gerenciamento_organizacao(
        usuario_logado, usuario.organizacao_id
    )
    if usuario_logado.get("loja_id") is not None:
        raise HTTPException(
            status_code=403,
            detail="Usuários vinculados a uma loja não podem alterar os dados globais da organização.",
        )
