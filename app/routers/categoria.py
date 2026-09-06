# app/routers/categorias.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.core.security import get_usuario_logado
from app.core.permissoes_loja import validar_mutacao_loja
from app.models.loja import Loja
from app.models.categoria import Categoria
from app.models.produto import Produto

router = APIRouter(prefix="/lojas", tags=["Categorias"])


class CategoriaCreate(BaseModel):
    nmcategoria: str
    dsicone: Optional[str] = "more_horiz"
    sitcategoria: Optional[str] = "ATIVA"
    idordcategoria: Optional[int] = 1


class CategoriaUpdate(BaseModel):
    nmcategoria: Optional[str] = None
    dsicone: Optional[str] = None
    sitcategoria: Optional[str] = None
    idordcategoria: Optional[int] = None


@router.get("/{loja_id}/categorias_todas")
def listar_categorias_por_loja_todas(loja_id: int, db: Session = Depends(get_db)):

    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    rows = (
        db.query(
            Categoria.categoria_id,
            Categoria.nmcategoria,
            Categoria.sitcategoria,
            Categoria.dsicone,
            Categoria.idordcategoria,
        )
        .filter(
            Categoria.organizacao_id == loja.organizacao_id,
        )
        .order_by(
            Categoria.idordcategoria.asc(),
            Categoria.nmcategoria.asc(),
        )
        .all()
    )

    return [
        {
            "categoria_id"   : r.categoria_id,
            "nmcategoria"    : r.nmcategoria,
            "sitcategoria"   : r.sitcategoria,
            "dsicone"        : r.dsicone,
            "idordcategoria" : r.idordcategoria,
        }
        for r in rows
    ]

@router.get("/{loja_id}/categorias")
def listar_categorias_por_loja(loja_id: int, db: Session = Depends(get_db)):

    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")

    rows = (
        db.query(
            Categoria.categoria_id,
            Categoria.nmcategoria,
            Categoria.idordcategoria,
            Categoria.dsicone,
        )
        .filter(
            Categoria.organizacao_id == loja.organizacao_id,
            Categoria.sitcategoria == "ATIVA",
        )
        .order_by(
            Categoria.idordcategoria.asc(),
            Categoria.nmcategoria.asc(),
        )
        .all()
    )

    return [
        {
            "categoria_id": r.categoria_id,
            "nmcategoria": r.nmcategoria,
            "idordcategoria": r.idordcategoria,
            "dsicone": r.dsicone,
        }
        for r in rows
    ]


@router.post("/{loja_id}/categorias")
def criar_categoria_por_loja(
    loja_id: int,
    payload: CategoriaCreate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    validar_mutacao_loja(usuario, loja.organizacao_id, loja_id)

    nome = payload.nmcategoria.strip()

    if not nome:
        raise HTTPException(status_code=400, detail="Nome da categoria é obrigatório.")

    if payload.sitcategoria not in ["ATIVA", "INATIVA"]:
        raise HTTPException(status_code=400, detail="Situação inválida.")

    categoria_existente = (
        db.query(Categoria)
        .filter(
            Categoria.organizacao_id == loja.organizacao_id,
            Categoria.nmcategoria == nome,
        )
        .first()
    )

    if categoria_existente:
        raise HTTPException(
            status_code=400,
            detail="Já existe uma categoria com esse nome nesta organização."
        )

    nova_categoria = Categoria(
        organizacao_id=loja.organizacao_id,
        nmcategoria=nome,
        dsicone=payload.dsicone,
        sitcategoria=payload.sitcategoria,
        idordcategoria=payload.idordcategoria,
    )

    db.add(nova_categoria)
    db.commit()
    db.refresh(nova_categoria)

    return {
        "message": "Categoria criada com sucesso.",
        "categoria_id": nova_categoria.categoria_id,
        "organizacao_id": nova_categoria.organizacao_id,
        "loja_id": loja_id,
        "nmcategoria": nova_categoria.nmcategoria,
        "dsicone": nova_categoria.dsicone,
        "sitcategoria": nova_categoria.sitcategoria,
        "idordcategoria": nova_categoria.idordcategoria,
        "dtcriacao": nova_categoria.dtcriacao,
    }


@router.put("/{loja_id}/categorias/{categoria_id}")
def atualizar_categoria_por_loja(
    loja_id: int,
    categoria_id: int,
    payload: CategoriaUpdate,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    validar_mutacao_loja(usuario, loja.organizacao_id, loja_id)

    categoria = (
        db.query(Categoria)
        .filter(
            Categoria.categoria_id == categoria_id,
            Categoria.organizacao_id == loja.organizacao_id,
        )
        .first()
    )

    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada para esta loja.")

    if payload.nmcategoria is not None:
        nome = payload.nmcategoria.strip()
        if not nome:
            raise HTTPException(status_code=400, detail="Nome da categoria é obrigatório.")

        categoria_existente = (
            db.query(Categoria)
            .filter(
                Categoria.organizacao_id == loja.organizacao_id,
                Categoria.nmcategoria == nome,
                Categoria.categoria_id != categoria_id,
            )
            .first()
        )

        if categoria_existente:
            raise HTTPException(
                status_code=400,
                detail="Já existe outra categoria com esse nome nesta organização."
            )

        categoria.nmcategoria = nome

    if payload.sitcategoria is not None:
        if payload.sitcategoria not in ["ATIVA", "INATIVA"]:
            raise HTTPException(status_code=400, detail="Situação inválida.")
        categoria.sitcategoria = payload.sitcategoria

    if payload.dsicone is not None:
        categoria.dsicone = payload.dsicone

    if payload.idordcategoria is not None:
        categoria.idordcategoria = payload.idordcategoria

    db.commit()
    db.refresh(categoria)

    return {
        "message": "Categoria atualizada com sucesso.",
        "categoria_id": categoria.categoria_id,
        "organizacao_id": categoria.organizacao_id,
        "loja_id": loja_id,
        "nmcategoria": categoria.nmcategoria,
        "dsicone": categoria.dsicone,
        "sitcategoria": categoria.sitcategoria,
        "idordcategoria": categoria.idordcategoria,
        "dtcriacao": categoria.dtcriacao,
        "dtultatu": categoria.dtultatu,
    }

@router.delete("/{loja_id}/categorias/{categoria_id}")
def deletar_categoria_por_loja(
    loja_id: int,
    categoria_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):

    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    categoria = db.query(Categoria).filter(
        Categoria.organizacao_id == loja.organizacao_id,
        Categoria.categoria_id == categoria_id,
    ).first()

    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada")
    validar_mutacao_loja(usuario, loja.organizacao_id, loja_id)

    existe_produto = db.query(Produto).filter(
        Produto.categoria_id == categoria_id,
    ).first()

    if existe_produto:
        raise HTTPException(
            status_code=400,
            detail="Não é possível deletar: existem produtos vinculados a essa categoria"
        )

    db.delete(categoria)
    db.commit()

    return {"mensagem": "Categoria deletada com sucesso"}

@router.patch("/{loja_id}/categorias/{categoria_id}/reativar")
def reativar_categoria_por_loja(
    loja_id: int,
    categoria_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail="Loja não encontrada")
    validar_mutacao_loja(usuario, loja.organizacao_id, loja_id)

    categoria = (
        db.query(Categoria)
        .filter(
            Categoria.categoria_id == categoria_id,
            Categoria.organizacao_id == loja.organizacao_id,
        )
        .first()
    )

    if not categoria:
        raise HTTPException(status_code=404, detail="Categoria não encontrada para esta loja.")

    if categoria.sitcategoria == "ATIVA":
        raise HTTPException(status_code=400, detail="Categoria já está ativa.")

    categoria.sitcategoria = "ATIVA"

    db.commit()
    db.refresh(categoria)

    return {
        "message": "Categoria reativada com sucesso.",
        "categoria_id": categoria.categoria_id,
        "loja_id": loja_id,
        "nmcategoria": categoria.nmcategoria,
        "dsicone": categoria.dsicone,
        "sitcategoria": categoria.sitcategoria,
        "dtultatu": categoria.dtultatu,
    }
