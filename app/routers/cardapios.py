from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP
import os
import uuid
from urllib.parse import urlparse

import requests

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field, model_validator
from typing import Literal
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_gerenciamento_organizacao, validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.core.config import PIXABAY_API_KEY, UPLOAD_PRODUTOS
from app.database import get_db
from app.models.cardapio import (
    Cardapio, CardapioItem, CardapioLoja, CardapioProgramacao, CardapioReajuste,
    CardapioVersao, CardapioVersaoCategoria,
)
from app.models.categoria import Categoria
from app.models.loja import Loja
from app.models.produto import Produto
from app.services.onboarding_parceiro_service import validar_publicacao_loja
from app.utils.datetime_utils import FUSO_BRASIL


router = APIRouter(tags=["Cardápios"])

_PIXABAY_URL = "https://pixabay.com/api/"
_PIXABAY_HEADERS = {
    "User-Agent": "Clubbar/1.0 (suporte@clubbar.com.br)",
}


def _consultar_pixabay(parametros: dict) -> dict:
    if not PIXABAY_API_KEY:
        raise HTTPException(
            503,
            "A busca de fotos padronizadas não está configurada.",
        )
    try:
        resposta = requests.get(
            _PIXABAY_URL,
            params={"key": PIXABAY_API_KEY, **parametros},
            headers=_PIXABAY_HEADERS,
            timeout=12,
        )
    except requests.RequestException:
        raise HTTPException(
            503,
            "Não foi possível consultar as fotos padronizadas agora.",
        )
    if resposta.status_code == 429:
        raise HTTPException(
            429,
            "O limite de busca de fotos foi atingido. Tente novamente em instantes.",
        )
    if resposta.status_code != 200:
        raise HTTPException(
            502,
            "Não foi possível consultar as fotos padronizadas agora.",
        )
    try:
        return resposta.json()
    except ValueError:
        raise HTTPException(502, "Resposta inválida da busca de fotos.")


def _url_pixabay_valida(url: str) -> bool:
    parsed = urlparse(url)
    dominio = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        dominio == "pixabay.com" or dominio.endswith(".pixabay.com")
    )


def _agora_brasilia() -> datetime:
    """Programações são cadastradas pelo parceiro no horário de Brasília."""
    return datetime.now(FUSO_BRASIL).replace(tzinfo=None)


class CardapioIn(BaseModel):
    nmcardapio: str = Field(min_length=2, max_length=120)
    tipocardapio: str = "PRINCIPAL"


class CardapioAtualizarIn(BaseModel):
    nmcardapio: str = Field(min_length=2, max_length=120)


class ProdutoOrganizacaoIn(BaseModel):
    nmproduto: str = Field(min_length=2, max_length=100)
    dsproduto: str | None = Field(default=None, max_length=255)
    sitproduto: Literal["ATIVO", "INATIVO"] = "ATIVO"
    skuproduto: str | None = Field(default=None, max_length=100)
    urlfotoproduto: str | None = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validar_valores(self):
        self.nmproduto = self.nmproduto.strip()
        self.dsproduto = (self.dsproduto or "").strip() or None
        self.skuproduto = (self.skuproduto or "").strip() or None
        self.urlfotoproduto = (self.urlfotoproduto or "").strip() or None
        if len(self.nmproduto) < 2:
            raise ValueError("Informe o nome do produto com pelo menos dois caracteres.")
        return self


class AssociarCardapioIn(BaseModel):
    cardapio_id: int = Field(gt=0)


class ItemIn(BaseModel):
    produto_id: int
    vrpreco: Decimal = Field(ge=0)
    tipodesconto: Literal["NENHUM", "PERCENTUAL", "VALOR"] = "NENHUM"
    vrdesconto: Decimal = Field(default=Decimal("0"), ge=0, max_digits=10, decimal_places=2)
    dtinidesconto: datetime | None = None
    dtfimdesconto: datetime | None = None
    qtcortesia: int | None = Field(default=None, ge=1)
    dtinicortesia: datetime | None = None
    dtfimcortesia: datetime | None = None
    pccashback: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    sititem: Literal["ATIVO", "INATIVO"] = "ATIVO"
    idorditem: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validar_desconto(self):
        if self.tipodesconto == "NENHUM":
            self.vrdesconto = Decimal("0")
            self.dtinidesconto = None
            self.dtfimdesconto = None
        elif self.tipodesconto == "PERCENTUAL" and self.vrdesconto > 100:
            raise ValueError("O desconto percentual não pode ultrapassar 100%.")
        elif self.tipodesconto == "VALOR" and self.vrdesconto > self.vrpreco:
            raise ValueError("O desconto não pode superar o preço do produto.")
        if self.dtinidesconto and self.dtfimdesconto and self.dtfimdesconto < self.dtinidesconto:
            raise ValueError("O fim do desconto deve ser posterior ao início.")
        eh_cortesia = (
            self.vrpreco == 0
            or (self.tipodesconto == "PERCENTUAL" and self.vrdesconto == 100)
            or (self.tipodesconto == "VALOR" and self.vrdesconto == self.vrpreco)
        )
        if eh_cortesia:
            if self.qtcortesia is None:
                raise ValueError("Informe a quantidade de cortesias disponibilizadas.")
            if self.dtinicortesia is None or self.dtfimcortesia is None:
                raise ValueError("Informe o período de disponibilidade das cortesias.")
            if self.dtfimcortesia <= self.dtinicortesia:
                raise ValueError("O fim das cortesias deve ser posterior ao início.")
        else:
            self.qtcortesia = None
            self.dtinicortesia = None
            self.dtfimcortesia = None
        return self


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

    @model_validator(mode="after")
    def validar_intervalo(self):
        if not self.dtinicio or not self.hrinicio:
            raise ValueError("Informe a data e o horário de início da exibição.")
        if not self.dtfim or not self.hrfim:
            raise ValueError("Informe a data e o horário de fim da exibição.")
        if self.dtfim and self.dtinicio and self.dtfim < self.dtinicio:
            raise ValueError("A data final deve ser igual ou posterior à inicial.")
        if (
            self.dtinicio
            and self.dtfim == self.dtinicio
            and self.hrinicio
            and self.hrfim
            and self.hrfim <= self.hrinicio
        ):
            raise ValueError("O horário final deve ser posterior ao horário inicial.")
        return self


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


def _cardapio(db: Session, cardapio_id: int, payload: dict | None = None) -> Cardapio:
    item = db.query(Cardapio).filter(Cardapio.cardapio_id == cardapio_id).first()
    if not item:
        raise HTTPException(404, "Cardápio não encontrado.")
    if payload is not None:
        validar_gerenciamento_organizacao(payload, item.organizacao_id)
        if int(payload.get("organizacao_id") or 0) != item.organizacao_id:
            raise HTTPException(403, "A organização não pertence ao usuário.")
    return item


def _associacao(db: Session, loja_id: int, cardapio_id: int, payload: dict | None = None) -> CardapioLoja:
    item = db.query(CardapioLoja).filter(
        CardapioLoja.loja_id == loja_id,
        CardapioLoja.cardapio_id == cardapio_id,
    ).first()
    if not item:
        raise HTTPException(404, "Associação de cardápio não encontrada.")
    if payload is not None:
        _loja(db, loja_id, payload)
    return item


def _versao(db: Session, versao_id: int, payload: dict | None = None) -> tuple[CardapioVersao, Cardapio]:
    versao = db.query(CardapioVersao).filter(CardapioVersao.cardapioversao_id == versao_id).first()
    if not versao:
        raise HTTPException(404, "Versão do cardápio não encontrada.")
    return versao, _cardapio(db, versao.cardapio_id, payload)


def _saida_cardapio(db: Session, item: Cardapio, associacao: CardapioLoja | None = None) -> dict:
    versoes = db.query(CardapioVersao).filter(CardapioVersao.cardapio_id == item.cardapio_id).order_by(CardapioVersao.nrversao.desc()).all()
    programacoes = db.query(CardapioProgramacao).filter(
        (CardapioProgramacao.cardapioloja_id == associacao.cardapioloja_id)
        if associacao else (CardapioProgramacao.cardapio_id == item.cardapio_id),
        CardapioProgramacao.sitprogramacao == "ATIVA",
    ).order_by(CardapioProgramacao.dtinicio.asc(), CardapioProgramacao.hrinicio.asc()).all()
    saida = {
        "cardapio_id": item.cardapio_id, "organizacao_id": item.organizacao_id,
        "loja_id": associacao.loja_id if associacao else None,
        "cardapioloja_id": associacao.cardapioloja_id if associacao else None,
        "nmcardapio": item.nmcardapio,
        "tipocardapio": item.tipocardapio,
        "sitcardapio": item.sitcardapio,
        "versoes": [{"cardapioversao_id": v.cardapioversao_id, "nrversao": v.nrversao, "statusversao": v.statusversao, "dtiniciovigencia": v.dtiniciovigencia, "dtfimvigencia": v.dtfimvigencia} for v in versoes],
        "programacoes": [_saida_programacao(programacao) for programacao in programacoes],
    }
    return saida


def _preco_final_item(item: CardapioItem, agora: datetime) -> tuple[Decimal, bool]:
    preco = Decimal(item.vrpreco)
    tipo = item.tipodesconto or "NENHUM"
    desconto = Decimal(item.vrdesconto or 0)
    ativo = (
        tipo != "NENHUM"
        and desconto > 0
        and (item.dtinidesconto is None or agora >= item.dtinidesconto)
        and (item.dtfimdesconto is None or agora <= item.dtfimdesconto)
    )
    if ativo and tipo == "PERCENTUAL":
        final = preco * (Decimal("1") - desconto / Decimal("100"))
    elif ativo and tipo == "VALOR":
        final = preco - desconto
    else:
        final = preco
    return max(Decimal("0"), final).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ativo


def _conteudo(
    db: Session,
    versao: CardapioVersao,
    cardapio: Cardapio,
    *,
    incluir_inativos: bool = False,
) -> dict:
    categorias = (
        db.query(CardapioVersaoCategoria, Categoria)
        .join(Categoria, Categoria.categoria_id == CardapioVersaoCategoria.categoria_id)
        .filter(CardapioVersaoCategoria.cardapioversao_id == versao.cardapioversao_id, Categoria.organizacao_id == cardapio.organizacao_id)
        .order_by(CardapioVersaoCategoria.idordcategoria)
        .all()
    )
    saida = []
    agora = _agora_brasilia()
    for vinculo, categoria in categorias:
        consulta_itens = (
            db.query(CardapioItem, Produto)
            .join(Produto, Produto.produto_id == CardapioItem.produto_id)
            .filter(
                CardapioItem.cardapioversaocategoria_id == vinculo.cardapioversaocategoria_id,
                Produto.organizacao_id == cardapio.organizacao_id,
            )
        )
        if not incluir_inativos:
            consulta_itens = consulta_itens.filter(CardapioItem.sititem == "ATIVO")
        itens = consulta_itens.order_by(CardapioItem.idorditem).all()
        produtos = []
        for ci, produto in itens:
            preco = Decimal(ci.vrpreco)
            tipo = ci.tipodesconto or "NENHUM"
            desconto = Decimal(ci.vrdesconto or 0)
            final, ativo = _preco_final_item(ci, agora)
            produtos.append({
                "cardapioitem_id": ci.cardapioitem_id,
                "produto_id": produto.produto_id,
                "organizacao_id": produto.organizacao_id,
                "loja_id": None,
                "categoria_id": categoria.categoria_id,
                "nmcategoria": categoria.nmcategoria,
                "nmproduto": produto.nmproduto,
                "dsproduto": produto.dsproduto,
                "skuproduto": produto.skuproduto,
                "urlfotoproduto": produto.urlfotoproduto,
                "vrpreco": float(preco),
                "vrprecoprod": float(preco),
                "vrprecofinal": float(final),
                "sititem": ci.sititem,
                "sitproduto": produto.sitproduto,
                "tipodesconto": tipo,
                "vrdesconto": float(desconto),
                "descontoativo": ativo,
                "pccashback": float(ci.pccashback) if ci.pccashback is not None else None,
                "dtinidesconto": ci.dtinidesconto,
                "dtfimdesconto": ci.dtfimdesconto,
                "qtcortesia": ci.qtcortesia,
                "dtinicortesia": ci.dtinicortesia,
                "dtfimcortesia": ci.dtfimcortesia,
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
    vinculos = db.query(CardapioLoja, Cardapio).join(
        Cardapio, Cardapio.cardapio_id == CardapioLoja.cardapio_id,
    ).filter(
        CardapioLoja.loja_id == loja_id,
        CardapioLoja.sitassociacao == "ATIVA",
    ).order_by(Cardapio.nmcardapio).all()
    return [_saida_cardapio(db, cardapio, vinculo) for vinculo, cardapio in vinculos]


def _quantidade_itens_cardapio(db: Session, cardapio_id: int) -> int:
    versao = db.query(CardapioVersao).filter(
        CardapioVersao.cardapio_id == cardapio_id,
    ).order_by(CardapioVersao.nrversao.desc()).first()
    return (
        db.query(CardapioItem).filter(CardapioItem.cardapioversao_id == versao.cardapioversao_id).count()
        if versao else 0
    )


@router.get("/organizacoes/{organizacao_id}/cardapios")
def listar_cardapios_empresa(organizacao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _validar_organizacao_do_produto(organizacao_id, payload)
    cardapios = db.query(Cardapio).filter(
        Cardapio.organizacao_id == organizacao_id,
    ).order_by(Cardapio.nmcardapio).all()
    resultado = []
    for cardapio in cardapios:
        lojas = db.query(CardapioLoja, Loja).join(Loja, Loja.loja_id == CardapioLoja.loja_id).filter(
            CardapioLoja.cardapio_id == cardapio.cardapio_id,
            CardapioLoja.sitassociacao == "ATIVA",
        ).order_by(Loja.nmloja).all()
        saida = _saida_cardapio(db, cardapio)
        saida.update({
            "quantidade_produtos": _quantidade_itens_cardapio(db, cardapio.cardapio_id),
            "lojas": [{
                "loja_id": loja.loja_id,
                "nmfantasialoja": loja.nmloja,
                "cardapioloja_id": vinculo.cardapioloja_id,
                "programacoes": [
                    _saida_programacao(programacao)
                    for programacao in db.query(CardapioProgramacao).filter(
                        CardapioProgramacao.cardapioloja_id == vinculo.cardapioloja_id,
                        CardapioProgramacao.sitprogramacao == "ATIVA",
                    ).order_by(CardapioProgramacao.dtinicio.asc()).all()
                ],
            } for vinculo, loja in lojas],
        })
        resultado.append(saida)
    return resultado


@router.post("/organizacoes/{organizacao_id}/cardapios", status_code=201)
def criar_cardapio_empresa(organizacao_id: int, dados: CardapioIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _validar_organizacao_do_produto(organizacao_id, payload)
    tipo = dados.tipocardapio.upper()
    if tipo not in {"PRINCIPAL", "ESPECIAL"}:
        raise HTTPException(422, "Tipo de cardápio inválido.")
    nome = dados.nmcardapio.strip()
    if db.query(Cardapio).filter(
        Cardapio.organizacao_id == organizacao_id,
        func.lower(Cardapio.nmcardapio) == nome.lower(),
    ).first():
        raise HTTPException(409, "Já existe um cardápio com esse nome na empresa.")
    cardapio = Cardapio(
        organizacao_id=organizacao_id,
        nmcardapio=nome,
        tipocardapio=tipo,
    )
    db.add(cardapio); db.flush()
    versao = CardapioVersao(cardapio_id=cardapio.cardapio_id, nrversao=1)
    db.add(versao); db.commit(); db.refresh(cardapio)
    return _saida_cardapio(db, cardapio)


@router.put("/cardapios/{cardapio_id}")
def atualizar_cardapio(cardapio_id: int, dados: CardapioAtualizarIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    cardapio = _cardapio(db, cardapio_id, payload)
    nome = dados.nmcardapio.strip()
    if db.query(Cardapio).filter(
        Cardapio.organizacao_id == cardapio.organizacao_id,
        func.lower(Cardapio.nmcardapio) == nome.lower(),
        Cardapio.cardapio_id != cardapio.cardapio_id,
    ).first():
        raise HTTPException(409, "Já existe outro cardápio com esse nome na empresa.")
    cardapio.nmcardapio = nome
    db.commit()
    db.refresh(cardapio)
    return _saida_cardapio(db, cardapio)


@router.get("/organizacoes/{organizacao_id}/produtos")
def listar_produtos_organizacao(organizacao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    validar_gerenciamento_organizacao(payload, organizacao_id)
    if int(payload.get("organizacao_id") or 0) != organizacao_id:
        raise HTTPException(403, "A organização não pertence ao usuário.")
    produtos = db.query(Produto).filter(Produto.organizacao_id == organizacao_id).order_by(Produto.nmproduto).all()
    return [_saida_produto_organizacao(p) for p in produtos]


def _saida_produto_organizacao(produto: Produto) -> dict:
    return {
        "produto_id": produto.produto_id,
        "organizacao_id": produto.organizacao_id,
        "nmproduto": produto.nmproduto,
        "dsproduto": produto.dsproduto,
        "sitproduto": produto.sitproduto,
        "skuproduto": produto.skuproduto,
        "urlfotoproduto": produto.urlfotoproduto,
        "dtcriacao": produto.dtcriacao,
        "dtultatu": produto.dtultatu,
    }


def _validar_organizacao_do_produto(organizacao_id: int, payload: dict) -> None:
    validar_gerenciamento_organizacao(payload, organizacao_id)
    if int(payload.get("organizacao_id") or 0) != organizacao_id:
        raise HTTPException(403, "A organização não pertence ao usuário.")


@router.get("/organizacoes/{organizacao_id}/produtos/fotos-pixabay")
def buscar_fotos_padronizadas_pixabay(
    organizacao_id: int,
    busca: str = Query(min_length=2, max_length=100),
    payload=Depends(get_usuario_logado),
):
    """Retorna opções de foto da Pixabay sem expor a chave ao aplicativo."""
    _validar_organizacao_do_produto(organizacao_id, payload)
    termo = busca.strip()
    if len(termo) < 2:
        raise HTTPException(422, "Informe pelo menos dois caracteres para buscar a foto.")
    dados = _consultar_pixabay({
        "q": termo,
        "lang": "pt",
        "image_type": "photo",
        "safesearch": "true",
        "order": "popular",
        "per_page": 24,
    })
    return {
        "fotos": [
            {
                "foto_id": foto.get("id"),
                "preview_url": foto.get("webformatURL") or foto.get("previewURL"),
                "pagina_url": foto.get("pageURL"),
                "autor": foto.get("user") or "Pixabay",
                "tags": foto.get("tags") or "",
            }
            for foto in dados.get("hits", [])
            if foto.get("id") and (foto.get("webformatURL") or foto.get("previewURL"))
        ],
    }


@router.post("/organizacoes/{organizacao_id}/produtos/fotos-pixabay/{foto_id}")
def importar_foto_padronizada_pixabay(
    organizacao_id: int,
    foto_id: int,
    payload=Depends(get_usuario_logado),
):
    """Copia a foto selecionada para o volume do Clubbar, evitando hotlinking."""
    _validar_organizacao_do_produto(organizacao_id, payload)
    if foto_id <= 0:
        raise HTTPException(422, "Foto inválida.")
    dados = _consultar_pixabay({"id": foto_id, "image_type": "photo"})
    fotos = dados.get("hits", [])
    if not fotos:
        raise HTTPException(404, "A foto escolhida não foi encontrada.")
    url = str(fotos[0].get("webformatURL") or "").strip()
    if not _url_pixabay_valida(url):
        raise HTTPException(502, "A foto escolhida não possui uma URL válida.")
    try:
        resposta = requests.get(
            url,
            headers=_PIXABAY_HEADERS,
            timeout=20,
            stream=True,
            allow_redirects=False,
        )
    except requests.RequestException:
        raise HTTPException(503, "Não foi possível baixar a foto escolhida.")
    tipo_conteudo = resposta.headers.get("content-type", "").split(";", 1)[0]
    extensoes = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    extensao = extensoes.get(tipo_conteudo)
    if resposta.status_code != 200 or extensao is None:
        raise HTTPException(502, "Não foi possível baixar a foto escolhida.")
    limite = 5 * 1024 * 1024
    conteudo = bytearray()
    for bloco in resposta.iter_content(chunk_size=64 * 1024):
        conteudo.extend(bloco)
        if len(conteudo) > limite:
            raise HTTPException(422, "A foto escolhida excede o limite de 5 MB.")
    if not conteudo:
        raise HTTPException(502, "Não foi possível baixar a foto escolhida.")
    os.makedirs(UPLOAD_PRODUTOS, exist_ok=True)
    nome = f"produto_pixabay_{uuid.uuid4().hex}{extensao}"
    with open(os.path.join(UPLOAD_PRODUTOS, nome), "wb") as arquivo:
        arquivo.write(conteudo)
    return {"urlfotoproduto": f"/uploads/produtos/{nome}"}


@router.post("/organizacoes/{organizacao_id}/produtos", status_code=201)
def criar_produto_organizacao(organizacao_id: int, dados: ProdutoOrganizacaoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _validar_organizacao_do_produto(organizacao_id, payload)
    existente = db.query(Produto).filter(
        Produto.organizacao_id == organizacao_id,
        func.lower(Produto.nmproduto) == dados.nmproduto.lower(),
    ).first()
    if existente:
        raise HTTPException(409, "Este produto já existe na organização.")
    campos = dados.model_dump()
    produto = Produto(organizacao_id=organizacao_id, **campos)
    db.add(produto)
    db.commit()
    db.refresh(produto)
    return _saida_produto_organizacao(produto)


@router.put("/organizacoes/{organizacao_id}/produtos/{produto_id}")
def alterar_produto_organizacao(organizacao_id: int, produto_id: int, dados: ProdutoOrganizacaoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _validar_organizacao_do_produto(organizacao_id, payload)
    produto = db.query(Produto).filter(
        Produto.produto_id == produto_id,
        Produto.organizacao_id == organizacao_id,
    ).first()
    if produto is None:
        raise HTTPException(404, "Produto não encontrado na organização.")
    for campo, valor in dados.model_dump().items():
        setattr(produto, campo, valor)
    db.commit()
    db.refresh(produto)
    return _saida_produto_organizacao(produto)


@router.post("/organizacoes/{organizacao_id}/produtos/foto")
async def enviar_foto_produto_organizacao(organizacao_id: int, foto: UploadFile = File(...), payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _validar_organizacao_do_produto(organizacao_id, payload)
    extensoes = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
    extensao = extensoes.get(foto.content_type or "")
    if extensao is None:
        raise HTTPException(422, "Escolha uma imagem JPG, PNG ou WebP.")
    conteudo = await foto.read(5 * 1024 * 1024 + 1)
    if not conteudo or len(conteudo) > 5 * 1024 * 1024:
        raise HTTPException(422, "A foto deve ter até 5 MB.")
    os.makedirs(UPLOAD_PRODUTOS, exist_ok=True)
    nome = f"produto_{uuid.uuid4().hex}{extensao}"
    with open(os.path.join(UPLOAD_PRODUTOS, nome), "wb") as arquivo:
        arquivo.write(conteudo)
    return {"urlfotoproduto": f"/uploads/produtos/{nome}"}


@router.post("/lojas/{loja_id}/cardapios/associar", status_code=201)
def associar(loja_id: int, dados: AssociarCardapioIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    loja = _loja(db, loja_id, payload)
    cardapio = db.query(Cardapio).filter(
        Cardapio.cardapio_id == dados.cardapio_id,
        Cardapio.organizacao_id == loja.organizacao_id,
        Cardapio.sitcardapio == "ATIVO",
    ).first()
    if not cardapio:
        raise HTTPException(404, "Cardápio não encontrado na organização.")
    if cardapio.tipocardapio == "PRINCIPAL":
        principal = db.query(CardapioLoja, Cardapio).join(
            Cardapio, Cardapio.cardapio_id == CardapioLoja.cardapio_id,
        ).filter(
            CardapioLoja.loja_id == loja.loja_id,
            CardapioLoja.sitassociacao == "ATIVA",
            Cardapio.tipocardapio == "PRINCIPAL",
            Cardapio.cardapio_id != cardapio.cardapio_id,
        ).first()
        if principal:
            raise HTTPException(409, "Este estabelecimento já possui um cardápio principal.")
    vinculo = db.query(CardapioLoja).filter(
        CardapioLoja.cardapio_id == cardapio.cardapio_id,
        CardapioLoja.loja_id == loja.loja_id,
    ).first()
    if vinculo is None:
        vinculo = CardapioLoja(
            cardapio_id=cardapio.cardapio_id,
            loja_id=loja.loja_id,
        )
        db.add(vinculo)
    else:
        vinculo.sitassociacao = "ATIVA"
    db.commit()
    db.refresh(vinculo)
    return _saida_cardapio(db, cardapio, vinculo)


@router.delete("/lojas/{loja_id}/cardapios/{cardapio_id}/associacao", status_code=204)
def remover_associacao(loja_id: int, cardapio_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    vinculo = _associacao(db, loja_id, cardapio_id, payload)
    vinculo.sitassociacao = "INATIVA"
    db.commit()


@router.post("/lojas/{loja_id}/cardapios", status_code=201)
def criar(loja_id: int, dados: CardapioIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _loja(db, loja_id, payload)
    raise HTTPException(403, "Crie o cardápio no menu da empresa e associe-o à loja.")


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
            db.add(CardapioItem(cardapioversao_id=nova.cardapioversao_id, cardapioversaocategoria_id=mapa[item.cardapioversaocategoria_id], produto_id=item.produto_id, vrpreco=item.vrpreco, tipodesconto=item.tipodesconto, vrdesconto=item.vrdesconto, dtinidesconto=item.dtinidesconto, dtfimdesconto=item.dtfimdesconto, qtcortesia=item.qtcortesia, dtinicortesia=item.dtinicortesia, dtfimcortesia=item.dtfimcortesia, pccashback=item.pccashback, sititem=item.sititem, idorditem=item.idorditem))
    db.commit(); db.refresh(nova)
    return _conteudo(db, nova, cardapio, incluir_inativos=True)


@router.get("/cardapios/versoes/{versao_id}")
def consultar_versao(versao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    versao, cardapio = _versao(db, versao_id, payload)
    return _conteudo(db, versao, cardapio, incluir_inativos=True)


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
            db.add(CardapioItem(cardapioversao_id=versao_id, cardapioversaocategoria_id=vinculo.cardapioversaocategoria_id, produto_id=item.produto_id, vrpreco=item.vrpreco, tipodesconto=item.tipodesconto, vrdesconto=item.vrdesconto, dtinidesconto=item.dtinidesconto, dtfimdesconto=item.dtfimdesconto, qtcortesia=item.qtcortesia, dtinicortesia=item.dtinicortesia, dtfimcortesia=item.dtfimcortesia, pccashback=item.pccashback, sititem=item.sititem, idorditem=item.idorditem))
    db.commit()
    return _conteudo(db, versao, cardapio, incluir_inativos=True)


@router.post("/cardapios/{cardapio_id}/programacoes", status_code=201)
def programar(cardapio_id: int, dados: ProgramacaoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    cardapio = _cardapio(db, cardapio_id, payload)
    if cardapio.tipocardapio == "PRINCIPAL":
        raise HTTPException(422, "O cardápio principal fica disponível continuamente e não utiliza programação.")
    item = CardapioProgramacao(cardapio_id=cardapio_id, **dados.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return _saida_programacao(item)


def _saida_programacao(item: CardapioProgramacao) -> dict:
    return {
        "cardapioprogramacao_id": item.cardapioprogramacao_id,
        "diasemana": item.diasemana,
        "dtinicio": item.dtinicio,
        "dtfim": item.dtfim,
        "hrinicio": item.hrinicio,
        "hrfim": item.hrfim,
        "sitprogramacao": item.sitprogramacao,
    }


def _inicio_programacao(item: ProgramacaoIn | CardapioProgramacao) -> datetime:
    return datetime.combine(item.dtinicio, item.hrinicio)


def _fim_programacao(item: ProgramacaoIn | CardapioProgramacao) -> datetime | None:
    if item.dtfim is None:
        return None
    return datetime.combine(item.dtfim, item.hrfim or time.max)


def _validar_sem_sobreposicao(
    db: Session,
    loja_id: int,
    cardapio_id: int,
    dados: ProgramacaoIn,
) -> None:
    """Impede dois cardápios especiais ativos no mesmo período da loja."""
    inicio = _inicio_programacao(dados)
    fim = _fim_programacao(dados)
    programacoes = db.query(CardapioProgramacao, CardapioLoja, Cardapio).join(
        CardapioLoja,
        CardapioLoja.cardapioloja_id == CardapioProgramacao.cardapioloja_id,
    ).join(
        Cardapio,
        Cardapio.cardapio_id == CardapioLoja.cardapio_id,
    ).filter(
        CardapioLoja.loja_id == loja_id,
        CardapioLoja.sitassociacao == "ATIVA",
        Cardapio.cardapio_id != cardapio_id,
        Cardapio.tipocardapio == "ESPECIAL",
        CardapioProgramacao.sitprogramacao == "ATIVA",
    ).all()
    for existente, _, _ in programacoes:
        inicio_existente = _inicio_programacao(existente)
        fim_existente = _fim_programacao(existente)
        if (fim is None or inicio_existente <= fim) and (
            fim_existente is None or inicio <= fim_existente
        ):
            raise HTTPException(
                409,
                "Este período se sobrepõe a outro cardápio especial da loja.",
            )


@router.get("/lojas/{loja_id}/cardapios/{cardapio_id}/programacoes")
def listar_programacoes_loja(loja_id: int, cardapio_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    vinculo = _associacao(db, loja_id, cardapio_id, payload)
    itens = db.query(CardapioProgramacao).filter(
        CardapioProgramacao.cardapioloja_id == vinculo.cardapioloja_id,
        CardapioProgramacao.sitprogramacao == "ATIVA",
    ).order_by(CardapioProgramacao.dtinicio.asc()).all()
    return [_saida_programacao(item) for item in itens]


@router.post("/lojas/{loja_id}/cardapios/{cardapio_id}/programacoes", status_code=201)
def programar_loja(loja_id: int, cardapio_id: int, dados: ProgramacaoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    vinculo = _associacao(db, loja_id, cardapio_id, payload)
    cardapio = _cardapio(db, cardapio_id, payload)
    if cardapio.tipocardapio == "PRINCIPAL":
        raise HTTPException(422, "O cardápio principal fica disponível continuamente e não utiliza programação.")
    _validar_sem_sobreposicao(db, loja_id, cardapio_id, dados)
    item = CardapioProgramacao(cardapioloja_id=vinculo.cardapioloja_id, **dados.model_dump())
    db.add(item); db.commit(); db.refresh(item)
    return _saida_programacao(item)


@router.delete("/lojas/{loja_id}/cardapios/{cardapio_id}/programacoes/{programacao_id}")
def remover_programacao_loja(loja_id: int, cardapio_id: int, programacao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    vinculo = _associacao(db, loja_id, cardapio_id, payload)
    item = db.query(CardapioProgramacao).filter(
        CardapioProgramacao.cardapioprogramacao_id == programacao_id,
        CardapioProgramacao.cardapioloja_id == vinculo.cardapioloja_id,
    ).first()
    if not item:
        raise HTTPException(404, "Programação não encontrada.")
    item.sitprogramacao = "INATIVA"
    db.commit()
    return {"mensagem": "Programação removida."}


@router.get("/cardapios/{cardapio_id}/programacoes")
def listar_programacoes(cardapio_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _cardapio(db, cardapio_id, payload)
    itens = db.query(CardapioProgramacao).filter(
        CardapioProgramacao.cardapio_id == cardapio_id,
        CardapioProgramacao.sitprogramacao == "ATIVA",
    ).order_by(CardapioProgramacao.dtinicio.asc()).all()
    return [_saida_programacao(item) for item in itens]


@router.delete("/cardapios/{cardapio_id}/programacoes/{programacao_id}")
def remover_programacao(cardapio_id: int, programacao_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _cardapio(db, cardapio_id, payload)
    item = db.query(CardapioProgramacao).filter(
        CardapioProgramacao.cardapioprogramacao_id == programacao_id,
        CardapioProgramacao.cardapio_id == cardapio_id,
    ).first()
    if not item:
        raise HTTPException(404, "Programação não encontrada.")
    item.sitprogramacao = "INATIVA"
    db.commit()
    return {"mensagem": "Programação removida."}


@router.post("/cardapios/versoes/{versao_id}/publicar")
def publicar(versao_id: int, dados: PublicarIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    versao, cardapio = _versao(db, versao_id, payload)
    associacoes = db.query(CardapioLoja).filter(
        CardapioLoja.cardapio_id == cardapio.cardapio_id,
        CardapioLoja.sitassociacao == "ATIVA",
    ).all()
    for associacao in associacoes:
        validar_publicacao_loja(db, associacao.loja_id)
    if versao.statusversao != "RASCUNHO":
        raise HTTPException(409, "Somente uma versão em rascunho pode ser publicada.")
    if not db.query(CardapioItem).filter(CardapioItem.cardapioversao_id == versao_id, CardapioItem.sititem == "ATIVO").first():
        raise HTTPException(422, "Inclua pelo menos um produto antes de publicar.")
    if cardapio.tipocardapio == "ESPECIAL":
        sem_programacao = [
            associacao for associacao in associacoes
            if not db.query(CardapioProgramacao).filter(
                CardapioProgramacao.cardapioloja_id == associacao.cardapioloja_id,
                CardapioProgramacao.sitprogramacao == "ATIVA",
            ).first()
        ]
        if sem_programacao:
            raise HTTPException(422, "Defina a programação do cardápio especial em cada loja associada antes de publicar.")
    versao.dtiniciovigencia, versao.dtfimvigencia = dados.dtinicio, dados.dtfim
    agora = _agora_brasilia()
    db.query(CardapioVersao).filter(CardapioVersao.cardapio_id == cardapio.cardapio_id, CardapioVersao.statusversao == "PUBLICADA").update({"statusversao": "SUBSTITUIDA"}, synchronize_session=False)
    versao.statusversao = "PROGRAMADA" if dados.dtinicio and dados.dtinicio > agora else "PUBLICADA"
    versao.dtpublicacao = agora
    db.commit()
    return {"statusversao": versao.statusversao, "mensagem": "Cardápio publicado com sucesso."}


@router.post("/cardapios/{cardapio_id}/retirar-publicacao")
def retirar_publicacao(cardapio_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    cardapio = _cardapio(db, cardapio_id, payload)
    quantidade = db.query(CardapioVersao).filter(
        CardapioVersao.cardapio_id == cardapio.cardapio_id,
        CardapioVersao.statusversao.in_(["PUBLICADA", "PROGRAMADA"]),
    ).update({"statusversao": "CANCELADA"}, synchronize_session=False)
    db.commit()
    if not quantidade:
        raise HTTPException(409, "Este cardápio não possui uma publicação ativa.")
    return {"mensagem": "Publicação retirada. O cardápio não ficará disponível aos clientes."}


@router.delete("/cardapios/{cardapio_id}", status_code=204)
def excluir_cardapio(cardapio_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    cardapio = _cardapio(db, cardapio_id, payload)
    versoes_ids = [
        item[0]
        for item in db.query(CardapioVersao.cardapioversao_id).filter(
            CardapioVersao.cardapio_id == cardapio.cardapio_id,
        ).all()
    ]
    if db.query(CardapioVersao).filter(
        CardapioVersao.cardapio_id == cardapio.cardapio_id,
        CardapioVersao.statusversao.in_(["PUBLICADA", "PROGRAMADA"]),
    ).first():
        raise HTTPException(409, "Retire a publicação antes de excluir este cardápio.")
    if versoes_ids:
        db.query(CardapioReajuste).filter(
            CardapioReajuste.cardapioversao_id.in_(versoes_ids),
        ).delete(synchronize_session=False)
    db.delete(cardapio)
    db.commit()


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
    return {"itens_alterados": len(itens), "conteudo": _conteudo(db, versao, cardapio, incluir_inativos=True)}


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
    agora = _agora_brasilia()
    cardapios = db.query(CardapioLoja, Cardapio).join(
        Cardapio, Cardapio.cardapio_id == CardapioLoja.cardapio_id,
    ).filter(
        CardapioLoja.loja_id == loja_id,
        CardapioLoja.sitassociacao == "ATIVA",
        Cardapio.sitcardapio == "ATIVO",
    ).order_by(Cardapio.cardapio_id).all()
    candidatos = []
    for associacao, cardapio in cardapios:
        programacoes = db.query(CardapioProgramacao).filter(
            CardapioProgramacao.cardapioloja_id == associacao.cardapioloja_id,
        ).all()
        if cardapio.tipocardapio != "PRINCIPAL" and not any(_programacao_valida(p, agora) for p in programacoes):
            continue
        versao = db.query(CardapioVersao).filter(CardapioVersao.cardapio_id == cardapio.cardapio_id, CardapioVersao.statusversao.in_(["PUBLICADA", "PROGRAMADA"]), func.coalesce(CardapioVersao.dtiniciovigencia, agora) <= agora).filter((CardapioVersao.dtfimvigencia.is_(None)) | (CardapioVersao.dtfimvigencia >= agora)).order_by(CardapioVersao.nrversao.desc()).first()
        if versao: candidatos.append((associacao, cardapio, versao))
    if not candidatos:
        raise HTTPException(404, "Nenhum cardápio publicado para esta loja no momento.")
    # Um especial vigente substitui o único cardápio principal da loja.
    # A validação de períodos impede mais de um especial vigente por vez.
    sazonais = [item for item in candidatos if item[1].tipocardapio != "PRINCIPAL"]
    selecionado = (sazonais or candidatos)[0]
    return _conteudo(db, selecionado[2], selecionado[1])
