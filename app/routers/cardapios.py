from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_gerenciamento_organizacao, validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cardapio import (
    Cardapio, CardapioItem, CardapioModelo, CardapioModeloItem, CardapioProgramacao, CardapioReajuste,
    CardapioVersao, CardapioVersaoCategoria,
)
from app.models.categoria import Categoria
from app.models.loja import Loja
from app.models.produto import Produto


router = APIRouter(tags=["Cardápios"])


class CardapioIn(BaseModel):
    nmcardapio: str = Field(min_length=2, max_length=120)
    tipocardapio: str = "PRINCIPAL"
    prioridade: int = Field(default=0, ge=0, le=999)


class ItemPadraoIn(BaseModel):
    nmcategoria: str = Field(min_length=2, max_length=120)
    nmproduto: str = Field(min_length=2, max_length=100)
    dsproduto: str | None = Field(default=None, max_length=255)
    vrpreco: Decimal = Field(ge=0)


class PrecoPadraoIn(BaseModel):
    vrpreco: Decimal = Field(ge=0)


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


def _conteudo(db: Session, versao: CardapioVersao, cardapio: Cardapio) -> dict:
    categorias = db.query(CardapioVersaoCategoria, Categoria).join(Categoria, Categoria.categoria_id == CardapioVersaoCategoria.categoria_id).filter(CardapioVersaoCategoria.cardapioversao_id == versao.cardapioversao_id).order_by(CardapioVersaoCategoria.idordcategoria).all()
    saida = []
    for vinculo, categoria in categorias:
        itens = db.query(CardapioItem, Produto).join(Produto, Produto.produto_id == CardapioItem.produto_id).filter(CardapioItem.cardapioversaocategoria_id == vinculo.cardapioversaocategoria_id, CardapioItem.sititem == "ATIVO").order_by(CardapioItem.idorditem).all()
        saida.append({"cardapioversaocategoria_id": vinculo.cardapioversaocategoria_id, "categoria_id": categoria.categoria_id, "nmcategoria": categoria.nmcategoria, "dsicone": categoria.dsicone, "idordcategoria": vinculo.idordcategoria, "itens": [{"cardapioitem_id": ci.cardapioitem_id, "produto_id": p.produto_id, "organizacao_id": p.organizacao_id, "loja_id": cardapio.loja_id, "categoria_id": categoria.categoria_id, "nmcategoria": categoria.nmcategoria, "nmproduto": p.nmproduto, "dsproduto": p.dsproduto, "urlfotoproduto": p.urlfotoproduto, "vrpreco": float(ci.vrpreco), "vrprecoprod": float(ci.vrpreco), "vrprecofinal": float(ci.vrpreco), "sitproduto": p.sitproduto, "tipodesconto": "NENHUM", "vrdesconto": 0.0, "descontoativo": False, "pccashback": float(p.pccashback) if p.pccashback is not None else None, "idorditem": ci.idorditem} for ci, p in itens]})
    return {"cardapio_id": cardapio.cardapio_id, "nmcardapio": cardapio.nmcardapio, "cardapioversao_id": versao.cardapioversao_id, "nrversao": versao.nrversao, "statusversao": versao.statusversao, "categorias": saida}


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
    return [{"cardapiomodelo_id": x.cardapiomodelo_id, "organizacao_id": x.organizacao_id, "nmcardapio": x.nmcardapio, "tipocardapio": x.tipocardapio, "sitcardapio": x.sitcardapio, "quantidade_produtos": db.query(CardapioModeloItem).filter(CardapioModeloItem.cardapiomodelo_id == x.cardapiomodelo_id).count()} for x in itens]


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


@router.get("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/itens")
def listar_itens_padrao(organizacao_id: int, modelo_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    linhas = db.query(CardapioModeloItem, Produto, Categoria).join(Produto, Produto.produto_id == CardapioModeloItem.produto_id).join(Categoria, Categoria.categoria_id == Produto.categoria_id).filter(CardapioModeloItem.cardapiomodelo_id == modelo_id).order_by(Categoria.idordcategoria, CardapioModeloItem.idorditem).all()
    return [{"cardapiomodeloitem_id": item.cardapiomodeloitem_id, "produto_id": produto.produto_id, "categoria_id": categoria.categoria_id, "nmcategoria": categoria.nmcategoria, "nmproduto": produto.nmproduto, "dsproduto": produto.dsproduto, "vrpreco": float(item.vrpreco)} for item, produto, categoria in linhas]


@router.post("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/itens", status_code=201)
def adicionar_item_padrao(organizacao_id: int, modelo_id: int, dados: ItemPadraoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    _validar_edicao_padrao(payload, organizacao_id)
    nome_categoria, nome_produto = dados.nmcategoria.strip(), dados.nmproduto.strip()
    if len(nome_categoria) < 2 or len(nome_produto) < 2:
        raise HTTPException(422, "Informe categoria e produto com pelo menos dois caracteres.")
    try:
        categoria = db.query(Categoria).filter(Categoria.organizacao_id == organizacao_id, func.lower(Categoria.nmcategoria) == nome_categoria.lower()).first()
        if categoria is None:
            categoria = Categoria(organizacao_id=organizacao_id, nmcategoria=nome_categoria, sitcategoria="ATIVA")
            db.add(categoria); db.flush()
        produto = db.query(Produto).filter(Produto.organizacao_id == organizacao_id, Produto.categoria_id == categoria.categoria_id, func.lower(Produto.nmproduto) == nome_produto.lower()).first()
        if produto is None:
            produto = Produto(organizacao_id=organizacao_id, categoria_id=categoria.categoria_id, nmproduto=nome_produto, dsproduto=dados.dsproduto, vrprecoprod=dados.vrpreco, sitproduto="ATIVO")
            db.add(produto); db.flush()
        if db.query(CardapioModeloItem).filter(CardapioModeloItem.cardapiomodelo_id == modelo_id, CardapioModeloItem.produto_id == produto.produto_id).first():
            raise HTTPException(409, "Este produto já está no cardápio padrão.")
        ordem = db.query(func.coalesce(func.max(CardapioModeloItem.idorditem), 0)).filter(CardapioModeloItem.cardapiomodelo_id == modelo_id).scalar()
        item = CardapioModeloItem(cardapiomodelo_id=modelo_id, produto_id=produto.produto_id, vrpreco=dados.vrpreco, idorditem=int(ordem) + 1)
        db.add(item); db.commit(); db.refresh(item)
        return {"cardapiomodeloitem_id": item.cardapiomodeloitem_id}
    except Exception:
        db.rollback()
        raise


@router.delete("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/itens/{item_id}", status_code=204)
def remover_item_padrao(organizacao_id: int, modelo_id: int, item_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    _validar_edicao_padrao(payload, organizacao_id)
    item = db.query(CardapioModeloItem).filter(CardapioModeloItem.cardapiomodelo_id == modelo_id, CardapioModeloItem.cardapiomodeloitem_id == item_id).first()
    if item is None:
        raise HTTPException(404, "Produto não encontrado neste cardápio.")
    db.delete(item); db.commit()


@router.put("/organizacoes/{organizacao_id}/cardapios-padrao/{modelo_id}/itens/{item_id}")
def alterar_preco_padrao(organizacao_id: int, modelo_id: int, item_id: int, dados: PrecoPadraoIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _modelo_organizacao(db, organizacao_id, modelo_id, payload)
    _validar_edicao_padrao(payload, organizacao_id)
    item = db.query(CardapioModeloItem).filter(CardapioModeloItem.cardapiomodelo_id == modelo_id, CardapioModeloItem.cardapiomodeloitem_id == item_id).first()
    if item is None:
        raise HTTPException(404, "Produto não encontrado neste cardápio.")
    item.vrpreco = dados.vrpreco
    db.commit()
    return {"cardapiomodeloitem_id": item.cardapiomodeloitem_id, "vrpreco": float(item.vrpreco)}


def _associar(db: Session, loja: Loja, modelo: CardapioModelo, prioridade: int) -> Cardapio:
    existente = db.query(Cardapio).filter(Cardapio.loja_id == loja.loja_id, Cardapio.cardapiomodelo_id == modelo.cardapiomodelo_id).first()
    if existente:
        return existente
    item = Cardapio(organizacao_id=loja.organizacao_id, loja_id=loja.loja_id, cardapiomodelo_id=modelo.cardapiomodelo_id, nmcardapio=modelo.nmcardapio, tipocardapio=modelo.tipocardapio, prioridade=prioridade)
    db.add(item); db.flush()
    versao = CardapioVersao(cardapio_id=item.cardapio_id, nrversao=1)
    db.add(versao); db.flush()
    itens = db.query(CardapioModeloItem, Produto).join(Produto, Produto.produto_id == CardapioModeloItem.produto_id).filter(CardapioModeloItem.cardapiomodelo_id == modelo.cardapiomodelo_id).order_by(CardapioModeloItem.idorditem).all()
    categorias = {}
    for vinculo, produto in itens:
        if produto.categoria_id not in categorias:
            categoria_versao = CardapioVersaoCategoria(cardapioversao_id=versao.cardapioversao_id, categoria_id=produto.categoria_id, idordcategoria=len(categorias) + 1)
            db.add(categoria_versao); db.flush()
            categorias[produto.categoria_id] = categoria_versao.cardapioversaocategoria_id
        db.add(CardapioItem(cardapioversao_id=versao.cardapioversao_id, cardapioversaocategoria_id=categorias[produto.categoria_id], produto_id=produto.produto_id, vrpreco=vinculo.vrpreco, idorditem=vinculo.idorditem))
    db.commit(); db.refresh(item)
    return item


@router.post("/lojas/{loja_id}/cardapios/associar", status_code=201)
def associar(loja_id: int, dados: AssociarCardapioIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    loja = _loja(db, loja_id, payload)
    modelo = db.query(CardapioModelo).filter(CardapioModelo.cardapiomodelo_id == dados.cardapiomodelo_id, CardapioModelo.organizacao_id == loja.organizacao_id, CardapioModelo.sitcardapio == "ATIVO").first()
    if not modelo: raise HTTPException(404, "Cardápio padrão não encontrado.")
    if not db.query(CardapioModeloItem).filter(CardapioModeloItem.cardapiomodelo_id == modelo.cardapiomodelo_id).first():
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
    if len(produtos_ids) != sum(len(c.itens) for c in dados.categorias):
        raise HTTPException(422, "Um produto não pode aparecer duas vezes na mesma versão.")
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
