from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cardapio import CategoriaPadrao
from app.models.categoria import Categoria


router = APIRouter(tags=["Categorias de cardápio"])


class SelecaoCategoriasIn(BaseModel):
    categorias_padrao_ids: list[int] = Field(default_factory=list)


class CategoriaPersonalizadaIn(BaseModel):
    nmcategoria: str = Field(min_length=2, max_length=120)
    dsicone: str | None = Field(default="more_horiz", max_length=50)


def _validar_organizacao(payload: dict, organizacao_id: int) -> None:
    try:
        organizacao_login = int(payload["organizacao_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(403, "Organização não identificada no login.")
    if organizacao_login != organizacao_id:
        raise HTTPException(403, "Acesso negado para esta organização.")


def _saida(item: Categoria) -> dict:
    return {
        "categoria_id": item.categoria_id,
        "organizacao_id": item.organizacao_id,
        "categoriapadrao_id": item.categoriapadrao_id,
        "nmcategoria": item.nmcategoria,
        "dsicone": item.dsicone,
        "sitcategoria": item.sitcategoria,
        "idordcategoria": item.idordcategoria,
    }


@router.get("/categorias-padrao")
def listar_padrao(db: Session = Depends(get_db)):
    itens = db.query(CategoriaPadrao).filter(
        CategoriaPadrao.sitcategoria == "ATIVA"
    ).order_by(CategoriaPadrao.idordcategoria, CategoriaPadrao.nmcategoria).all()
    return [
        {
            "categoriapadrao_id": item.categoriapadrao_id,
            "nmcategoria": item.nmcategoria,
            "dsicone": item.dsicone,
            "idordcategoria": item.idordcategoria,
        }
        for item in itens
    ]


@router.get("/organizacoes/{organizacao_id}/categorias")
def listar_organizacao(organizacao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _validar_organizacao(payload, organizacao_id)
    itens = db.query(Categoria).filter(
        Categoria.organizacao_id == organizacao_id
    ).order_by(Categoria.idordcategoria, Categoria.nmcategoria).all()
    return [_saida(item) for item in itens]


@router.post("/organizacoes/{organizacao_id}/categorias/selecionar")
def selecionar_padrao(organizacao_id: int, dados: SelecaoCategoriasIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _validar_organizacao(payload, organizacao_id)
    ids = set(dados.categorias_padrao_ids)
    padroes = db.query(CategoriaPadrao).filter(
        CategoriaPadrao.categoriapadrao_id.in_(ids),
        CategoriaPadrao.sitcategoria == "ATIVA",
    ).all() if ids else []
    if len(padroes) != len(ids):
        raise HTTPException(422, "Uma ou mais categorias padrão são inválidas.")
    existentes = {
        item.categoriapadrao_id: item
        for item in db.query(Categoria).filter(
            Categoria.organizacao_id == organizacao_id,
            Categoria.categoriapadrao_id.isnot(None),
        ).all()
    }
    for item in existentes.values():
        item.sitcategoria = "ATIVA" if item.categoriapadrao_id in ids else "INATIVA"
    for padrao in padroes:
        if padrao.categoriapadrao_id not in existentes:
            db.add(Categoria(
                organizacao_id=organizacao_id,
                categoriapadrao_id=padrao.categoriapadrao_id,
                nmcategoria=padrao.nmcategoria,
                dsicone=padrao.dsicone,
                sitcategoria="ATIVA",
                idordcategoria=padrao.idordcategoria,
            ))
    db.commit()
    return listar_organizacao(organizacao_id, payload, db)


@router.post("/organizacoes/{organizacao_id}/categorias", status_code=201)
def criar_personalizada(organizacao_id: int, dados: CategoriaPersonalizadaIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _validar_organizacao(payload, organizacao_id)
    nome = dados.nmcategoria.strip()
    if db.query(Categoria).filter(
        Categoria.organizacao_id == organizacao_id,
        Categoria.nmcategoria == nome,
    ).first():
        raise HTTPException(409, "Já existe uma categoria com este nome na organização.")
    proxima_ordem = db.query(Categoria).filter(Categoria.organizacao_id == organizacao_id).count() + 1
    item = Categoria(
        organizacao_id=organizacao_id,
        nmcategoria=nome,
        dsicone=dados.dsicone or "more_horiz",
        sitcategoria="ATIVA",
        idordcategoria=proxima_ordem,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _saida(item)
