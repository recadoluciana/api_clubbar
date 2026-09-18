from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_gerenciamento_organizacao, validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.core.config import UPLOAD_PRODUTOS
from app.database import get_db
from app.models.cardapio import (
    Cardapio, CardapioItem, CardapioModelo, CardapioProgramacao, CardapioReajuste,
    CardapioVersao, CardapioVersaoCategoria,
)
from app.models.categoria import Categoria
from app.models.cardapio_padrao import CardapioModeloCategoria, CardapioModeloProduto
from app.models.loja import Loja
from app.models.produto import Produto


router = APIRouter(tags=["Cardápios"])


class CardapioIn(BaseModel):
    nmcardapio: str = Field(min_length=2, max_length=120)
    tipocardapio: str = "PRINCIPAL"
    prioridade: int = Field(default=0, ge=0, le=999)


class ItemPadraoIn(BaseModel):
    cardapiomodelocategoria_id: int = Field(gt=0)
    produto_id: int | None = Field(default=None, gt=0)
    nmproduto: str = Field(min_length=2, max_length=100)
    dsproduto: str | None = Field(default=None, max_length=255)
    vrprecoprod: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    sitproduto: Literal["ATIVO", "INATIVO"] = "ATIVO"
    skuproduto: str | None = Field(default=None, max_length=100)
    urlfotoproduto: str | None = Field(default=None, max_length=255)
    tipodesconto: Literal["NENHUM", "PERCENTUAL", "VALOR"] = "NENHUM"
    vrdesconto: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    pccashback: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    dtinidesconto: datetime | None = None
    dtfimdesconto: datetime | None = None

    @model_validator(mode="after")
    def validar_valores(self):
        self.nmproduto = self.nmproduto.strip()
        self.dsproduto = (self.dsproduto or "").strip() or None
        self.skuproduto = (self.skuproduto or "").strip() or None
        self.urlfotoproduto = (self.urlfotoproduto or "").strip() or None
        if len(self.nmproduto) < 2:
            raise ValueError("Informe o nome do produto com pelo menos dois caracteres.")
        if self.tipodesconto == "NENHUM":
            self.vrdesconto = Decimal("0")
            self.dtinidesconto = None
            self.dtfimdesconto = None
        elif self.tipodesconto == "PERCENTUAL" and self.vrdesconto > 100:
            raise ValueError("O desconto percentual não pode ultrapassar 100%.")
        elif self.tipodesconto == "VALOR" and self.vrdesconto > self.vrprecoprod:
            raise ValueError("O desconto não pode superar o preço do produto.")
        if self.dtinidesconto and self.dtfimdesconto and self.dtfimdesconto < self.dtinidesconto:
            raise ValueError("O fim do desconto deve ser posterior ao início.")
        return self


class AssociarCardapioIn(BaseModel):
    cardapiomodelo_id: int
    prioridade: int = Field(default=0, ge=0, le=999)


class ItemIn(BaseModel):
    produto_id: int
    vrpreco: Decimal = Field(ge=0)
    idorditem: int = Field(default=1, ge=1)


class CategoriaVersaoIn(BaseModel):
    categoria_id: int
    idordcategoria: int = Field(default=1, ge=1)
    itens: list[ItemIn] = Field(default_factory=list)


class ConteudoVersaoIn(BaseModel):
    categorias: list[CategoriaVersaoIn] = Field(default_factory=list)


class PublicarIn(BaseModel):
    dtinicio: datetime | None = None
    dtfim: datetime | None = None


class ProgramacaoIn(BaseModel):
    diasemana: int | None = Field(default=None, ge=1, le=7)
    dtinicio: date | None = None
    dtfim: date | None = None
    hrinicio: time | None = None
    hrfim: time | None = None


class ReajusteIn(BaseModel):
    categoria_id: int | None = None
    tipoajuste: str = "PERCENTUAL"
    operacao: str = "AUMENTO"
    valorajuste: Decimal = Field(gt=0)
    arredondamento: int = Field(default=2, ge=0, le=2)


def _loja(db: Session, loja_id: int, payload: dict | None = None) -> Loja:
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(404, "Loja não encontrada.")
    if payload is not None:
        validar_mutacao_loja(payload, loja.organizacao_id, loja.loja_id)
    return loja


def _validar_edicao_padrao(payload: dict, organizacao_id: int) -> None:
    validar_gerenciamento_organizacao(payload, organizacao_id)
    if (
        int(payload.get("organizacao_id") or 0) != organizacao_id
        or payload.get("loja_id") is not None
        or str(payload.get("dscargo") or "").upper() not in {"SUPERADMIN", "ADMIN"}
    ):
        raise HTTPException(403, "Somente administradores da empresa podem editar o cardápio padrão.")


def _cardapio(db: Session, cardapio_id: int, payload: dict | None = None) -> Cardapio:
    item = db.query(Cardapio).filter(Cardapio.cardapio_id == cardapio_id).first()
    if not item:
        raise HTTPException(404, "Cardápio não encontrado.")
    _loja(db, item.loja_id, payload)
    return item


def _versao(db: Session, versao_id: int, payload: dict | None = None) -> tuple[CardapioVersao, Cardapio]:
    versao = db.query(CardapioVersao).filter(CardapioVersao.cardapioversao_id == versao_id).first()
    if not versao:
        raise HTTPException(404, "Versão do cardápio não encontrada.")
    return versao, _cardapio(db, versao.cardapio_id, payload)


def _saida_cardapio(db: Session, item: Cardapio) -> dict:
    versoes = db.query(CardapioVersao).filter(CardapioVersao.cardapio_id == item.cardapio_id).order_by(CardapioVersao.nrversao.desc()).all()
    return {
        "cardapio_id": item.cardapio_id, "organizacao_id": item.organizacao_id,
        "loja_id": item.loja_id, "cardapiomodelo_id": item.cardapiomodelo_id,
        "nmcardapio": item.nmcardapio,
        "tipocardapio": item.tipocardapio, "prioridade": item.prioridade,
        "sitcardapio": item.sitcardapio,
        "versoes": [{"cardapioversao_id": v.cardapioversao_id, "nrversao": v.nrversao, "statusversao": v.statusversao, "dtiniciovigencia": v.dtiniciovigencia, "dtfimvigencia": v.dtfimvigencia} for v in versoes],
    }


def _preco_final_item(preco: Decimal, produto: Produto, agora: datetime) -> tuple[Decimal, bool]:
    tipo = produto.tipodesconto or "NENHUM"
    desconto = Decimal(produto.vrdesconto or 0)
    ativo = (
        tipo != "NENHUM"
        and desconto > 0
        and (produto.dtinidesconto is None or agora >= produto.dtinidesconto)
        and (produto.dtfimdesconto is None or agora <= produto.dtfimdesconto)
    )
    if ativo and tipo == "PERCENTUAL":
        final = preco * (Decimal("1") - desconto / Decimal("100"))
    elif ativo and tipo == "VALOR":
        final = preco - desconto
    else:
        final = preco
    return max(Decimal("0"), final).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ativo


def _conteudo(db: Session, versao: CardapioVersao, cardapio: Cardapio) -> dict:
    categorias = (
        db.query(CardapioVersaoCategoria, Categoria)
        .join(Categoria, Categoria.categoria_id == CardapioVersaoCategoria.categoria_id)
        .filter(CardapioVersaoCategoria.cardapioversao_id == versao.cardapioversao_id, Categoria.organizacao_id == cardapio.organizacao_id)
        .order_by(CardapioVersaoCategoria.idordcategoria)
        .all()
    )
    saida = []
    agora = datetime.now()
    for vinculo, categoria in categorias:
        itens = (
            db.query(CardapioItem, Produto)
            .join(Produto, Produto.produto_id == CardapioItem.produto_id)
            .filter(
                CardapioItem.cardapioversaocategoria_id == vinculo.cardapioversaocategoria_id,
                CardapioItem.sititem == "ATIVO",
                Produto.organizacao_id == cardapio.organizacao_id,
            )
            .order_by(CardapioItem.idorditem)
            .all()
        )
        produtos = []
        for ci, produto in itens:
            tipo = produto.tipodesconto or "NENHUM"
            desconto = Decimal(produto.vrdesconto or 0)
            preco = Decimal(ci.vrpreco)
            final, ativo = _preco_final_item(preco, produto, agora)
            produtos.append({
                "cardapioitem_id": ci.cardapioitem_id,
                "produto_id": produto.produto_id,
                "organizacao_id": produto.organizacao_id,
                "loja_id": cardapio.loja_id,
                "categoria_id": categoria.categoria_id,
                "nmcategoria": categoria.nmcategoria,
                "nmproduto": produto.nmproduto,
                "dsproduto": produto.dsproduto,
                "skuproduto": produto.skuproduto,
                "urlfotoproduto": produto.urlfotoproduto,
                "vrpreco": float(preco),
                "vrprecoprod": float(preco),
                "vrprecofinal": float(final),
                "sitproduto": produto.sitproduto,
                "tipodesconto": tipo,
                "vrdesconto": float(desconto),
                "descontoativo": ativo,
                "pccashback": float(produto.pccashback) if produto.pccashback is not None else None,
                "dtinidesconto": produto.dtinidesconto,
                "dtfimdesconto": produto.dtfimdesconto,
                "dtcriacao": produto.dtcriacao,
                "dtultatu": produto.dtultatu,
                "idorditem": ci.idorditem,
            })
        saida.append({
            "cardapioversaocategoria_id": vinculo.cardapioversaocategoria_id,
            "categoria_id": categoria.categoria_id,
            "nmcategoria": categoria.nmcategoria,
            "dsicone": categoria.dsicone,
            "idordcategoria": vinculo.idordcategoria,
            "itens": produtos,
        })
    return {
        "cardapio_id": cardapio.cardapio_id,
        "nmcardapio": cardapio.nmcardapio,
        "cardapioversao_id": versao.cardapioversao_id,
        "nrversao": versao.nrversao,
        "statusversao": versao.statusversao,
        "categorias": saida,
    }


@router.get("/lojas/{loja_id}/cardapios")
def listar(loja_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _loja(db, loja_id, payload)
    return [_saida_cardapio(db, item) for item in db.query(Cardapio).filter(Cardapio.loja_id == loja_id).order_by(Cardapio.prioridade.desc(), Cardapio.nmcardapio).all()]


@router.get("/organizacoes/{organizacao_id}/cardapios-padrao")
def listar_padroes(organizacao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    validar_gerenciamento_organizacao(payload, organizacao_id)
    if int(payload.get("organizacao_id") or 0) != organizacao_id:
        raise HTTPException(403, "A organização não pertence ao usuário.")
    itens = db.query(CardapioModelo).filter(CardapioModelo.organizacao_id == organizacao_id).order_by(CardapioModelo.nmcardapio).all()
    return [{"cardapiomodelo_id": x.cardapiomodelo_id, "organizacao_id": x.organizacao_id, "nmcardapio": x.nmcardapio, "tipocardapio": x.tipocardapio, "sitcardapio": x.sitcardapio, "quantidade_produtos": db.query(CardapioModeloProduto).join(CardapioModeloCategoria, CardapioModeloCategoria.cardapiomodelocategoria_id == CardapioModeloProduto.cardapiomodelocategoria_id).filter(CardapioModeloCategoria.cardapiomodelo_id == x.cardapiomodelo_id).count()} for x in itens]


@router.post("/organizacoes/{organizacao_id}/cardapios-padrao", status_code=201)
def criar_padrao(organizacao_id: int, dados: CardapioIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _validar_edicao_padrao(payload, organizacao_id)
    tipo = dados.tipocardapio.upper()
    if tipo not in {"PRINCIPAL", "ESPECIAL", "SAZONAL", "EVENTO"}:
        raise HTTPException(422, "Tipo de cardápio inválido.")
    nome = dados.nmcardapio.strip()
    if db.query(CardapioModelo).filter(CardapioModelo.organizacao_id == organizacao_id, func.lower(CardapioModelo.nmcardapio) == nome.lower()).first():
        raise HTTPException(409, "Já existe um cardápio padrão com esse nome.")
    item = CardapioModelo(organizacao_id=organizacao_id, nmcardapio=nome, tipocardapio=tipo)
    db.add(item); db.commit(); db.refresh(item)
    return {"cardapiomodelo_id": item.cardapiomodelo_id, "organizacao_id": item.organizacao_id, "nmcardapio": item.nmcardapio, "tipocardapio": item.tipocardapio, "sitcardapio": item.sitcardapio}


def _modelo_organizacao(db: Session, organizacao_id: int, modelo_id: int, payload: dict) -> CardapioModelo:
    validar_gerenciamento_organizacao(payload, organizacao_id)
    if int(payload.get("organizacao_id") or 0) != organizacao_id:
        raise HTTPException(403, "A organização não pertence ao usuário.")
    modelo = db.query(CardapioModelo).filter(CardapioModelo.cardapiomodelo_id == modelo_id, CardapioModelo.organizacao_id == organizacao_id).first()
    if not modelo:
        raise HTTPException(404, "Cardápio padrão não encontrado.")
    return modelo


class CategoriaDoPadraoIn(BaseModel):
    categoria_id: int = Field(gt=0)


def _categoria_do_padrao(db: Session, organizacao_id: int, modelo_id: int, categoria_padrao_id: int) -> CardapioModeloCategoria:
    item = db.query(CardapioModeloCategoria).filter(
        CardapioModeloCategoria.cardapiomodelocategoria_id == categoria_padrao_id,
        CardapioModeloCategoria.cardapiomodelo_id == modelo_id,
        CardapioModeloCategoria.organizacao_id == organizacao_id,
    ).first()
    if item is None:
        raise HTTPException(404, "Categoria não encontrada neste cardápio padrão.")
    return item


@router.get("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/categorias")
def listar_categorias_padrao(organizacao_id: int, modelo_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    categorias = db.query(CardapioModeloCategoria, Categoria).join(Categoria, Categoria.categoria_id == CardapioModeloCategoria.categoria_id).filter(
        CardapioModeloCategoria.cardapiomodelo_id == modelo_id,
    ).order_by(CardapioModeloCategoria.idordcategoria).all()
    return [{
        "cardapiomodelocategoria_id": c.cardapiomodelocategoria_id,
        "categoria_id": c.categoria_id,
        "nmcategoria": origem.nmcategoria,
        "dsicone": origem.dsicone,
        "quantidade_produtos": db.query(CardapioModeloProduto).filter(CardapioModeloProduto.cardapiomodelocategoria_id == c.cardapiomodelocategoria_id).count(),
    } for c, origem in categorias]


@router.post("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/categorias", status_code=201)
def adicionar_categoria_padrao(organizacao_id: int, modelo_id: int, dados: CategoriaDoPadraoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    _validar_edicao_padrao(payload, organizacao_id)
    categoria = _categoria_produto_padrao(db, organizacao_id, dados.categoria_id)
    if db.query(CardapioModeloCategoria).filter(
        CardapioModeloCategoria.cardapiomodelo_id == modelo_id,
        CardapioModeloCategoria.categoria_id == categoria.categoria_id,
    ).first():
        raise HTTPException(409, "Esta categoria já está no cardápio padrão.")
    ordem = db.query(func.coalesce(func.max(CardapioModeloCategoria.idordcategoria), 0)).filter(CardapioModeloCategoria.cardapiomodelo_id == modelo_id).scalar()
    item = CardapioModeloCategoria(
        organizacao_id=organizacao_id, cardapiomodelo_id=modelo_id,
        categoria_id=categoria.categoria_id, idordcategoria=int(ordem) + 1,
    )
    db.add(item); db.commit(); db.refresh(item)
    return {"cardapiomodelocategoria_id": item.cardapiomodelocategoria_id, "categoria_id": item.categoria_id, "nmcategoria": categoria.nmcategoria, "dsicone": categoria.dsicone, "quantidade_produtos": 0}


@router.delete("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/categorias/{categoria_padrao_id}")
def remover_categoria_padrao(organizacao_id: int, modelo_id: int, categoria_padrao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    _validar_edicao_padrao(payload, organizacao_id)
    categoria = _categoria_do_padrao(db, organizacao_id, modelo_id, categoria_padrao_id)
    vinculos = db.query(CardapioModeloProduto).filter(CardapioModeloProduto.cardapiomodelocategoria_id == categoria_padrao_id).all()
    quantidade = len(vinculos)
    for vinculo in vinculos:
        db.delete(vinculo)
    db.delete(categoria)
    db.commit()
    return {"categorias_excluidas": 1, "vinculos_excluidos": quantidade, "produtos_excluidos": 0}


@router.get("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/itens")
def listar_itens_padrao(organizacao_id: int, modelo_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    linhas = db.query(CardapioModeloProduto, Produto, CardapioModeloCategoria, Categoria).join(Produto, Produto.produto_id == CardapioModeloProduto.produto_id).join(CardapioModeloCategoria, CardapioModeloCategoria.cardapiomodelocategoria_id == CardapioModeloProduto.cardapiomodelocategoria_id).join(Categoria, Categoria.categoria_id == CardapioModeloCategoria.categoria_id).filter(CardapioModeloCategoria.cardapiomodelo_id == modelo_id, Produto.organizacao_id == organizacao_id).order_by(CardapioModeloCategoria.idordcategoria, CardapioModeloProduto.idorditem).all()
    return [_saida_item_padrao(vinculo, produto, categoria, origem) for vinculo, produto, categoria, origem in linhas]


def _saida_item_padrao(vinculo: CardapioModeloProduto, produto: Produto, categoria: CardapioModeloCategoria, origem: Categoria) -> dict:
    return {
        "cardapiomodeloproduto_id": vinculo.cardapiomodeloproduto_id,
        "produto_id": produto.produto_id,
        "cardapiomodelocategoria_id": categoria.cardapiomodelocategoria_id,
        "organizacao_id": produto.organizacao_id,
        "categoria_id": categoria.categoria_id,
        "nmcategoria": origem.nmcategoria,
        "nmproduto": produto.nmproduto,
        "dsproduto": produto.dsproduto,
        "vrprecoprod": float(produto.vrprecoprod),
        "vrpreco": float(produto.vrprecoprod),
        "sitproduto": produto.sitproduto,
        "skuproduto": produto.skuproduto,
        "urlfotoproduto": produto.urlfotoproduto,
        "tipodesconto": produto.tipodesconto,
        "vrdesconto": float(produto.vrdesconto or 0),
        "pccashback": float(produto.pccashback) if produto.pccashback is not None else None,
        "dtinidesconto": produto.dtinidesconto,
        "dtfimdesconto": produto.dtfimdesconto,
        "dtcriacao": produto.dtcriacao,
        "dtultatu": produto.dtultatu,
    }


def _categoria_produto_padrao(db: Session, organizacao_id: int, categoria_id: int) -> Categoria:
    categoria = db.query(Categoria).filter(Categoria.organizacao_id == organizacao_id, Categoria.categoria_id == categoria_id, Categoria.sitcategoria == "ATIVA").first()
    if categoria is None:
        raise HTTPException(422, "Selecione uma categoria ativa da organização.")
    return categoria


@router.get("/organizacoes/{organizacao_id}/produtos")
def listar_produtos_organizacao(organizacao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    validar_gerenciamento_organizacao(payload, organizacao_id)
    if int(payload.get("organizacao_id") or 0) != organizacao_id:
        raise HTTPException(403, "A organização não pertence ao usuário.")
    produtos = db.query(Produto).filter(Produto.organizacao_id == organizacao_id).order_by(Produto.nmproduto).all()
    return [{"produto_id": p.produto_id, "nmproduto": p.nmproduto, "dsproduto": p.dsproduto, "vrprecoprod": float(p.vrprecoprod), "sitproduto": p.sitproduto, "skuproduto": p.skuproduto, "urlfotoproduto": p.urlfotoproduto, "tipodesconto": p.tipodesconto, "vrdesconto": float(p.vrdesconto or 0), "pccashback": float(p.pccashback) if p.pccashback is not None else None, "dtinidesconto": p.dtinidesconto, "dtfimdesconto": p.dtfimdesconto} for p in produtos]


@router.post("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/itens", status_code=201)
def adicionar_item_padrao(organizacao_id: int, modelo_id: int, dados: ItemPadraoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    _validar_edicao_padrao(payload, organizacao_id)
    categoria = _categoria_do_padrao(db, organizacao_id, modelo_id, dados.cardapiomodelocategoria_id)
    try:
        if dados.produto_id is not None:
            produto = db.query(Produto).filter(Produto.produto_id == dados.produto_id, Produto.organizacao_id == organizacao_id).first()
            if produto is None:
                raise HTTPException(404, "Produto não encontrado na organização.")
        else:
            if db.query(Produto).filter(Produto.organizacao_id == organizacao_id, func.lower(Produto.nmproduto) == dados.nmproduto.lower()).first():
                raise HTTPException(409, "Este produto já existe na organização. Selecione-o para utilizar neste cardápio.")
            campos = dados.model_dump(exclude={"cardapiomodelocategoria_id", "produto_id"})
            produto = Produto(organizacao_id=organizacao_id, **campos)
            db.add(produto); db.flush()
        if db.query(CardapioModeloProduto).filter(CardapioModeloProduto.cardapiomodelocategoria_id == categoria.cardapiomodelocategoria_id, CardapioModeloProduto.produto_id == produto.produto_id).first():
            raise HTTPException(409, "Este produto já está nesta categoria do cardápio.")
        ordem = db.query(func.coalesce(func.max(CardapioModeloProduto.idorditem), 0)).filter(CardapioModeloProduto.cardapiomodelocategoria_id == categoria.cardapiomodelocategoria_id).scalar()
        vinculo = CardapioModeloProduto(cardapiomodelocategoria_id=categoria.cardapiomodelocategoria_id, produto_id=produto.produto_id, idorditem=int(ordem) + 1)
        db.add(vinculo); db.commit(); db.refresh(vinculo)
        origem = db.get(Categoria, categoria.categoria_id)
        return _saida_item_padrao(vinculo, produto, categoria, origem)
    except Exception:
        db.rollback()
        raise


@router.delete("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/itens/{item_id}", status_code=204)
def remover_item_padrao(organizacao_id: int, modelo_id: int, item_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    _validar_edicao_padrao(payload, organizacao_id)
    vinculo, _, _, _ = _produto_do_padrao(db, organizacao_id, modelo_id, item_id)
    db.delete(vinculo)
    db.commit()


def _produto_do_padrao(db: Session, organizacao_id: int, modelo_id: int, item_id: int):
    linha = db.query(CardapioModeloProduto, Produto, CardapioModeloCategoria, Categoria).join(Produto, Produto.produto_id == CardapioModeloProduto.produto_id).join(CardapioModeloCategoria, CardapioModeloCategoria.cardapiomodelocategoria_id == CardapioModeloProduto.cardapiomodelocategoria_id).join(Categoria, Categoria.categoria_id == CardapioModeloCategoria.categoria_id).filter(
        CardapioModeloProduto.cardapiomodeloproduto_id == item_id,
        CardapioModeloCategoria.cardapiomodelo_id == modelo_id,
        CardapioModeloCategoria.organizacao_id == organizacao_id,
        Produto.organizacao_id == organizacao_id,
    ).first()
    if linha is None:
        raise HTTPException(404, "Produto não encontrado neste cardápio.")
    return linha


@router.put("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/itens/{item_id}")
def alterar_produto_padrao(organizacao_id: int, modelo_id: int, item_id: int, dados: ItemPadraoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    _validar_edicao_padrao(payload, organizacao_id)
    vinculo, produto, _, _ = _produto_do_padrao(db, organizacao_id, modelo_id, item_id)
    categoria = _categoria_do_padrao(db, organizacao_id, modelo_id, dados.cardapiomodelocategoria_id)
    if dados.produto_id is not None and dados.produto_id != produto.produto_id:
        raise HTTPException(422, "O produto do vínculo não pode ser trocado nesta edição.")
    for campo, valor in dados.model_dump(exclude={"cardapiomodelocategoria_id", "produto_id"}).items():
        setattr(produto, campo, valor)
    vinculo.cardapiomodelocategoria_id = categoria.cardapiomodelocategoria_id
    db.commit()
    db.refresh(produto)
    origem = db.get(Categoria, categoria.categoria_id)
    return _saida_item_padrao(vinculo, produto, categoria, origem)


@router.post("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/foto")
async def enviar_foto_produto_padrao(organizacao_id: int, modelo_id: int, foto: UploadFile = File(...), payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    _validar_edicao_padrao(payload, organizacao_id)
    extensoes = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    extensao = extensoes.get(foto.content_type or "")
    if extensao is None:
        raise HTTPException(422, "Escolha uma imagem JPG, PNG ou WebP.")
    conteudo = await foto.read(5 * 1024 * 1024 + 1)
    if not conteudo or len(conteudo) > 5 * 1024 * 1024:
        raise HTTPException(422, "A foto deve ter até 5 MB.")
    os.makedirs(UPLOAD_PRODUTOS, exist_ok=True)
    nome = f"padrao_{uuid.uuid4().hex}{extensao}"
    with open(os.path.join(UPLOAD_PRODUTOS, nome), "wb") as arquivo:
        arquivo.write(conteudo)
    return {"urlfotoproduto": f"/uploads/produtos/{nome}"}


def _associar(db: Session, loja: Loja, modelo: CardapioModelo, prioridade: int) -> Cardapio:
    existente = db.query(Cardapio).filter(Cardapio.loja_id == loja.loja_id, Cardapio.cardapiomodelo_id == modelo.cardapiomodelo_id).first()
    if existente:
        return existente
    item = Cardapio(organizacao_id=loja.organizacao_id, loja_id=loja.loja_id, cardapiomodelo_id=modelo.cardapiomodelo_id, nmcardapio=modelo.nmcardapio, tipocardapio=modelo.tipocardapio, prioridade=prioridade)
    db.add(item); db.flush()
    versao = CardapioVersao(cardapio_id=item.cardapio_id, nrversao=1)
    db.add(versao); db.flush()
    categorias = db.query(CardapioModeloCategoria).filter(CardapioModeloCategoria.cardapiomodelo_id == modelo.cardapiomodelo_id).order_by(CardapioModeloCategoria.idordcategoria).all()
    for categoria in categorias:
        categoria_versao = CardapioVersaoCategoria(cardapioversao_id=versao.cardapioversao_id, categoria_id=categoria.categoria_id, idordcategoria=categoria.idordcategoria)
        db.add(categoria_versao); db.flush()
        produtos = db.query(CardapioModeloProduto, Produto).join(Produto, Produto.produto_id == CardapioModeloProduto.produto_id).filter(CardapioModeloProduto.cardapiomodelocategoria_id == categoria.cardapiomodelocategoria_id, Produto.organizacao_id == loja.organizacao_id).order_by(CardapioModeloProduto.idorditem).all()
        for vinculo, produto in produtos:
            db.add(CardapioItem(cardapioversao_id=versao.cardapioversao_id, cardapioversaocategoria_id=categoria_versao.cardapioversaocategoria_id, produto_id=produto.produto_id, vrpreco=produto.vrprecoprod, idorditem=vinculo.idorditem))
    db.commit(); db.refresh(item)
    return item


@router.post("/lojas/{loja_id}/cardapios/associar", status_code=201)
def associar(loja_id: int, dados: AssociarCardapioIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    loja = _loja(db, loja_id, payload)
    modelo = db.query(CardapioModelo).filter(CardapioModelo.cardapiomodelo_id == dados.cardapiomodelo_id, CardapioModelo.organizacao_id == loja.organizacao_id, CardapioModelo.sitcardapio == "ATIVO").first()
    if not modelo: raise HTTPException(404, "Cardápio padrão não encontrado.")
    if not db.query(CardapioModeloProduto).join(CardapioModeloCategoria, CardapioModeloCategoria.cardapiomodelocategoria_id == CardapioModeloProduto.cardapiomodelocategoria_id).filter(CardapioModeloCategoria.cardapiomodelo_id == modelo.cardapiomodelo_id).first():
        raise HTTPException(422, "Adicione produtos ao cardápio padrão antes de utilizá-lo em uma loja.")
    return _saida_cardapio(db, _associar(db, loja, modelo, dados.prioridade))


@router.post("/lojas/{loja_id}/cardapios", status_code=201)
def criar(loja_id: int, dados: CardapioIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _loja(db, loja_id, payload)
    raise HTTPException(403, "Crie o cardápio padrão no menu da empresa e associe-o à loja.")


@router.post("/cardapios/{cardapio_id}/nova-versao", status_code=201)
def nova_versao(cardapio_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    cardapio = _cardapio(db, cardapio_id, payload)
    origem = db.query(CardapioVersao).filter(CardapioVersao.cardapio_id == cardapio_id).order_by(CardapioVersao.nrversao.desc()).first()
    numero = (origem.nrversao if origem else 0) + 1
    nova = CardapioVersao(cardapio_id=cardapio_id, nrversao=numero)
    db.add(nova); db.flush()
    if origem:
        mapa = {}
        for cat in db.query(CardapioVersaoCategoria).filter(CardapioVersaoCategoria.cardapioversao_id == origem.cardapioversao_id).all():
            nc = CardapioVersaoCategoria(cardapioversao_id=nova.cardapioversao_id, categoria_id=cat.categoria_id, idordcategoria=cat.idordcategoria)
            db.add(nc); db.flush(); mapa[cat.cardapioversaocategoria_id] = nc.cardapioversaocategoria_id
        for item in db.query(CardapioItem).filter(CardapioItem.cardapioversao_id == origem.cardapioversao_id).all():
            db.add(CardapioItem(cardapioversao_id=nova.cardapioversao_id, cardapioversaocategoria_id=mapa[item.cardapioversaocategoria_id], produto_id=item.produto_id, vrpreco=item.vrpreco, sititem=item.sititem, idorditem=item.idorditem))
    db.commit(); db.refresh(nova)
    return _conteudo(db, nova, cardapio)


@router.get("/cardapios/versoes/{versao_id}")
def consultar_versao(versao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    versao, cardapio = _versao(db, versao_id, payload)
    return _conteudo(db, versao, cardapio)


@router.put("/cardapios/versoes/{versao_id}/conteudo")
def salvar_conteudo(versao_id: int, dados: ConteudoVersaoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    versao, cardapio = _versao(db, versao_id, payload)
    if versao.statusversao != "RASCUNHO":
        raise HTTPException(409, "Somente uma versão em rascunho pode ser alterada.")
    categorias_ids = {c.categoria_id for c in dados.categorias}
    produtos_ids = {i.produto_id for c in dados.categorias for i in c.itens}
    for categoria in dados.categorias:
        if len({item.produto_id for item in categoria.itens}) != len(categoria.itens):
            raise HTTPException(422, "Um produto não pode aparecer duas vezes na mesma categoria.")
    if db.query(Categoria).filter(Categoria.categoria_id.in_(categorias_ids), Categoria.organizacao_id == cardapio.organizacao_id).count() != len(categorias_ids):
        raise HTTPException(422, "Uma ou mais categorias não pertencem à organização.")
    if db.query(Produto).filter(Produto.produto_id.in_(produtos_ids), Produto.organizacao_id == cardapio.organizacao_id).count() != len(produtos_ids):
        raise HTTPException(422, "Um ou mais produtos não pertencem à organização.")
    db.query(CardapioVersaoCategoria).filter(CardapioVersaoCategoria.cardapioversao_id == versao_id).delete(synchronize_session=False)
    db.flush()
    for categoria in dados.categorias:
        vinculo = CardapioVersaoCategoria(cardapioversao_id=versao_id, categoria_id=categoria.categoria_id, idordcategoria=categoria.idordcategoria)
        db.add(vinculo); db.flush()
        for item in categoria.itens:
            db.add(CardapioItem(cardapioversao_id=versao_id, cardapioversaocategoria_id=vinculo.cardapioversaocategoria_id, produto_id=item.produto_id, vrpreco=item.vrpreco, idorditem=item.idorditem))
    db.commit()
    return _conteudo(db, versao, cardapio)


@router.post("/cardapios/{cardapio_id}/programacoes", status_code=201)
def programar(cardapio_id: int, dados: ProgramacaoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _cardapio(db, cardapio_id, payload)
    if dados.dtfim and dados.dtinicio and dados.dtfim < dados.dtinicio:
        raise HTTPException(422, "A data final deve ser igual ou posterior à inicial.")
    item = CardapioProgramacao(cardapio_id=cardapio_id, **dados.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return {"cardapioprogramacao_id": item.cardapioprogramacao_id, **dados.model_dump()}


@router.post("/cardapios/versoes/{versao_id}/publicar")
def publicar(versao_id: int, dados: PublicarIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    versao, cardapio = _versao(db, versao_id, payload)
    if versao.statusversao != "RASCUNHO":
        raise HTTPException(409, "Somente uma versão em rascunho pode ser publicada.")
    if not db.query(CardapioItem).filter(CardapioItem.cardapioversao_id == versao_id, CardapioItem.sititem == "ATIVO").first():
        raise HTTPException(422, "Inclua pelo menos um produto antes de publicar.")
    versao.dtiniciovigencia, versao.dtfimvigencia = dados.dtinicio, dados.dtfim
    agora = datetime.now()
    db.query(CardapioVersao).filter(CardapioVersao.cardapio_id == cardapio.cardapio_id, CardapioVersao.statusversao == "PUBLICADA").update({"statusversao": "SUBSTITUIDA"}, synchronize_session=False)
    versao.statusversao = "PROGRAMADA" if dados.dtinicio and dados.dtinicio > agora else "PUBLICADA"
    versao.dtpublicacao = agora
    db.commit()
    return {"statusversao": versao.statusversao, "mensagem": "Cardápio publicado com sucesso."}


@router.post("/cardapios/versoes/{versao_id}/reajustar")
def reajustar(versao_id: int, dados: ReajusteIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    versao, cardapio = _versao(db, versao_id, payload)
    if versao.statusversao != "RASCUNHO":
        raise HTTPException(409, "Crie uma nova versão antes de reajustar preços publicados.")
    if dados.tipoajuste not in {"PERCENTUAL", "VALOR"} or dados.operacao not in {"AUMENTO", "REDUCAO"}:
        raise HTTPException(422, "Configuração de reajuste inválida.")
    query = db.query(CardapioItem).join(CardapioVersaoCategoria).filter(CardapioItem.cardapioversao_id == versao_id)
    if dados.categoria_id:
        query = query.filter(CardapioVersaoCategoria.categoria_id == dados.categoria_id)
    itens = query.all()
    sinal = Decimal("1") if dados.operacao == "AUMENTO" else Decimal("-1")
    unidade = Decimal("1").scaleb(-dados.arredondamento)
    for item in itens:
        atual = Decimal(item.vrpreco)
        delta = atual * dados.valorajuste / Decimal("100") if dados.tipoajuste == "PERCENTUAL" else dados.valorajuste
        novo = (atual + sinal * delta).quantize(unidade, rounding=ROUND_HALF_UP)
        if novo < 0:
            raise HTTPException(422, "O reajuste resultaria em preço negativo.")
        item.vrpreco = novo
    db.add(CardapioReajuste(cardapioversao_id=versao_id, categoria_id=dados.categoria_id, usuario_id=int(payload["sub"]), tipoajuste=dados.tipoajuste, operacao=dados.operacao, valorajuste=dados.valorajuste, arredondamento=dados.arredondamento, qtitensalterados=len(itens)))
    db.commit()
    return {"itens_alterados": len(itens), "conteudo": _conteudo(db, versao, cardapio)}


def _programacao_valida(item: CardapioProgramacao, agora: datetime) -> bool:
    if item.sitprogramacao != "ATIVA": return False
    if item.diasemana and item.diasemana != agora.isoweekday(): return False
    if item.dtinicio and agora.date() < item.dtinicio: return False
    if item.dtfim and agora.date() > item.dtfim: return False
    if item.hrinicio and agora.time() < item.hrinicio: return False
    if item.hrfim and agora.time() > item.hrfim: return False
    return True


@router.get("/lojas/{loja_id}/cardapio-publicado")
def cardapio_publicado(loja_id: int, db: Session=Depends(get_db)):
    _loja(db, loja_id)
    agora = datetime.now()
    cardapios = db.query(Cardapio).filter(Cardapio.loja_id == loja_id, Cardapio.sitcardapio == "ATIVO").order_by(Cardapio.prioridade.desc()).all()
    candidatos = []
    for cardapio in cardapios:
        programacoes = db.query(CardapioProgramacao).filter(CardapioProgramacao.cardapio_id == cardapio.cardapio_id).all()
        if cardapio.tipocardapio != "PRINCIPAL" and not any(_programacao_valida(p, agora) for p in programacoes):
            continue
        versao = db.query(CardapioVersao).filter(CardapioVersao.cardapio_id == cardapio.cardapio_id, CardapioVersao.statusversao.in_(["PUBLICADA", "PROGRAMADA"]), func.coalesce(CardapioVersao.dtiniciovigencia, agora) <= agora).filter((CardapioVersao.dtfimvigencia.is_(None)) | (CardapioVersao.dtfimvigencia >= agora)).order_by(CardapioVersao.nrversao.desc()).first()
        if versao: candidatos.append((cardapio, versao))
    if not candidatos:
        raise HTTPException(404, "Nenhum cardápio publicado para esta loja no momento.")
    return _conteudo(db, candidatos[0][1], candidatos[0][0])
