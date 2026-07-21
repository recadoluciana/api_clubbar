from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate, UsuarioOut
from app.core.security import hash_senha
from app.models.loja import Loja


router = APIRouter(tags=["Usuários"])


CARGOS_VALIDOS = {
    "SUPERADMIN",
    "ADMIN",
    "GERENTE",
    "CAIXA",
    "BARMAN",
    "GARCOM",
    "PORTEIRO",
}


def _normalizar_email(email: str) -> str:
    return email.strip().lower()


def _normalizar_cargo(cargo: str) -> str:
    return cargo.strip().upper()


def _validar_cargo(cargo: str) -> str:
    cargo_normalizado = _normalizar_cargo(cargo)

    if cargo_normalizado not in CARGOS_VALIDOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cargo inválido.",
        )

    return cargo_normalizado


def _validar_loja_da_organizacao(
    db: Session,
    *,
    organizacao_id: int,
    loja_id: int | None,
) -> None:
    if loja_id is None:
        return

    loja = (
        db.query(Loja)
        .filter(
            Loja.loja_id == loja_id,
            Loja.organizacao_id == organizacao_id,
        )
        .first()
    )

    if not loja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A loja informada não pertence a esta organização.",
        )


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
        .filter(
            Usuario.organizacao_id == organizacao_id,
        )
        .order_by(
            Usuario.usuario_id.asc(),
            Usuario.nmusuario.asc(),
        )
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
    nome = payload.nmusuario.strip()
    email = _normalizar_email(payload.emailuser)
    cargo = _validar_cargo(
        payload.dscargo or "BARMAN",
    )

    if not nome:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe o nome do usuário.",
        )

    email_existente = (
        db.query(Usuario)
        .filter(
            Usuario.emailuser == email,
        )
        .first()
    )

    if email_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um usuário com este e-mail.",
        )

    _validar_loja_da_organizacao(
        db,
        organizacao_id=organizacao_id,
        loja_id=payload.loja_id,
    )

    novo = Usuario(
        organizacao_id=organizacao_id,
        loja_id=payload.loja_id,
        nmusuario=nome,
        emailuser=email,
        senhahashuser=hash_senha(
            payload.senha,
        ),
        dscargo=cargo,
        situsuario=(
            payload.situsuario or "ATIVO"
        ).strip().upper(),
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado para esta organização.",
        )

    # ---------------------------------------------------------
    # E-MAIL
    # ---------------------------------------------------------

    if payload.emailuser is not None:
        email = _normalizar_email(
            payload.emailuser,
        )

        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe o e-mail do usuário.",
            )

        if email != usuario.emailuser:
            email_existente = (
                db.query(Usuario)
                .filter(
                    Usuario.emailuser == email,
                    Usuario.usuario_id != usuario_id,
                )
                .first()
            )

            if email_existente:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Já existe outro usuário com este e-mail.",
                )

        usuario.emailuser = email

    # ---------------------------------------------------------
    # NOME
    # ---------------------------------------------------------

    if payload.nmusuario is not None:
        nome = payload.nmusuario.strip()

        if not nome:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Informe o nome do usuário.",
            )

        usuario.nmusuario = nome

    # ---------------------------------------------------------
    # LOJA
    # ---------------------------------------------------------

    # Permite inclusive remover o vínculo da loja.
    if "loja_id" in payload.model_fields_set:
        _validar_loja_da_organizacao(
            db,
            organizacao_id=organizacao_id,
            loja_id=payload.loja_id,
        )

        usuario.loja_id = payload.loja_id

    # ---------------------------------------------------------
    # CARGO
    # ---------------------------------------------------------

    if payload.dscargo is not None:
        novo_cargo = _validar_cargo(
            payload.dscargo,
        )

        if usuario_id == 1:
            if novo_cargo != usuario.dscargo:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "O cargo do usuário principal "
                        "não pode ser alterado."
                    ),
                )
        else:
            usuario.dscargo = novo_cargo

    # ---------------------------------------------------------
    # STATUS
    # ---------------------------------------------------------

    if payload.situsuario is not None:
        usuario.situsuario = (
            payload.situsuario
            .strip()
            .upper()
        )

    # ---------------------------------------------------------
    # SENHA
    # ---------------------------------------------------------

    if (
        payload.senha is not None
        and payload.senha.strip()
    ):
        usuario.senhahashuser = hash_senha(
            payload.senha.strip(),
        )

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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não encontrado para esta organização.",
        )

    if usuario_id == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O usuário principal do sistema não pode ser excluído.",
        )

    db.delete(usuario)
    db.commit()

    return {
        "detail": "Usuário excluído com sucesso."
    }


@router.get(
    "/usuarios/{usuario_id}/loja",
)
def buscar_loja_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
):
    resultado = (
        db.query(
            Usuario,
            Loja,
        )
        .join(
            Loja,
            Loja.loja_id == Usuario.loja_id,
        )
        .filter(
            Usuario.usuario_id == usuario_id,
        )
        .first()
    )

    if not resultado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Loja do usuário não encontrada.",
        )

    usuario, loja = resultado

    return {
        "usuario_id": usuario.usuario_id,
        "loja_id": loja.loja_id,
        "nmloja": loja.nmloja or "",
        "urllogoloja": loja.urllogoloja or "",
    }