from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate, UsuarioOut
from app.core.security import gerar_hash_senha

router = APIRouter(tags=["Usuarios"])

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate, UsuarioOut
from app.core.security import gerar_hash_senha

router = APIRouter(tags=["Usuários"])

@router.get(
    "/organizacoes/{organizacao_id}/usuarios",
    response_model=list[UsuarioOut],
)
def listar_usuarios_por_organizacao(
    organizacao_id: int,
    db: Session = Depends(get_db),
):
    usuarios = (
        db.query(Usuario)
        .filter(Usuario.organizacao_id == organizacao_id)
        .order_by(Usuario.nmusuario.asc())
        .all()
    )

    return usuarios

@router.post(
    "/organizacoes/{organizacao_id}/usuarios",
    response_model=UsuarioOut,
    status_code=status.HTTP_201_CREATED,
)
def criar_usuario_por_organizacao(
    organizacao_id: int,
    payload: UsuarioCreate,
    db: Session = Depends(get_db),
):
    email_existente = (
        db.query(Usuario)
        .filter(Usuario.emailuser == payload.emailuser)
        .first()
    )
    if email_existente:
        raise HTTPException(
            status_code=400,
            detail="Já existe usuário com este e-mail",
        )

    novo = Usuario(
        organizacao_id=organizacao_id,
        loja_id=payload.loja_id,
        nmusuario=payload.nmusuario,
        emailuser=payload.emailuser,
        senhahashuser=gerar_hash_senha(payload.senha),
        dscargo=payload.dscargo or "FUNCIONARIO",
        situsuario=payload.situsuario or "ATIVO",
    )

    db.add(novo)
    db.commit()
    db.refresh(novo)

    return novo

@router.put(
    "/organizacoes/{organizacao_id}/usuarios/{usuario_id}",
    response_model=UsuarioOut,
)
def atualizar_usuario_por_organizacao(
    organizacao_id: int,
    usuario_id: int,
    payload: UsuarioUpdate,
    db: Session = Depends(get_db),
):
    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.usuario_id == usuario_id,
            Usuario.organizacao_id == organizacao_id,
        )
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado para esta organização",
        )

    if payload.emailuser and payload.emailuser != usuario.emailuser:
        email_existente = (
            db.query(Usuario)
            .filter(
                Usuario.emailuser == payload.emailuser,
                Usuario.usuario_id != usuario_id,
            )
            .first()
        )
        if email_existente:
            raise HTTPException(
                status_code=400,
                detail="Já existe usuário com este e-mail",
            )

    if payload.loja_id is not None:
        usuario.loja_id = payload.loja_id

    if payload.nmusuario is not None:
        usuario.nmusuario = payload.nmusuario

    if payload.emailuser is not None:
        usuario.emailuser = payload.emailuser

    if payload.dscargo is not None:
        usuario.dscargo = payload.dscargo

    if payload.situsuario is not None:
        usuario.situsuario = payload.situsuario

    if payload.senha is not None and payload.senha.strip():
        usuario.senhahashuser = gerar_hash_senha(payload.senha)

    db.commit()
    db.refresh(usuario)

    return usuario

@router.delete(
    "/organizacoes/{organizacao_id}/usuarios/{usuario_id}",
    status_code=status.HTTP_200_OK,
)
def deletar_usuario_por_organizacao(
    organizacao_id: int,
    usuario_id: int,
    db: Session = Depends(get_db),
):
    usuario = (
        db.query(Usuario)
        .filter(
            Usuario.usuario_id == usuario_id,
            Usuario.organizacao_id == organizacao_id,
        )
        .first()
    )

    if not usuario:
        raise HTTPException(
            status_code=404,
            detail="Usuário não encontrado para esta organização",
        )

    usuario.situsuario = "INATIVO"
    db.commit()
    db.refresh(usuario)

    return {"detail": "Usuário inativado com sucesso"}

