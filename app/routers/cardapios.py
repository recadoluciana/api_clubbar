from datetime import date, datetime, time
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cardapio import (
    Cardapio, CardapioItem, CardapioProgramacao, CardapioReajuste,
    CardapioVersao, CardapioVersaoCategoria,
)
from app.models.categoria import Categoria
from app.models.loja import Loja
from app.models.produto import Produto
from app.services.onboarding_parceiro_service import validar_publicacao_loja


router = APIRouter(tags=["Cardápios"])


class CardapioIn(BaseModel):
    nmcardapio: str = Field(min_length=2, max_length=120)
    tipocardapio: str = "PRINCIPAL"
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
    publicar_apos_aprovacao: bool = False
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
        "loja_id": item.loja_id, "nmcardapio": item.nmcardapio,
        "tipocardapio": item.tipocardapio, "prioridade": item.prioridade,
        "sitcardapio": item.sitcardapio,
        "versoes": [{"cardapioversao_id": v.cardapioversao_id, "nrversao": v.nrversao, "statusversao": v.statusversao, "dtiniciovigencia": v.dtiniciovigencia, "dtfimvigencia": v.dtfimvigencia} for v in versoes],
    }


def _conteudo(db: Session, versao: CardapioVersao, cardapio: Cardapio) -> dict:
    categorias = db.query(CardapioVersaoCategoria, Categoria).join(Categoria, Categoria.categoria_id == CardapioVersaoCategoria.categoria_id).filter(CardapioVersaoCategoria.cardapioversao_id == versao.cardapioversao_id).order_by(CardapioVersaoCategoria.idordcategoria).all()
    saida = []
    for vinculo, categoria in categorias:
        itens = db.query(CardapioItem, Produto).join(Produto, Produto.produto_id == CardapioItem.produto_id).filter(CardapioItem.cardapioversaocategoria_id == vinculo.cardapioversaocategoria_id, CardapioItem.sititem == "ATIVO").order_by(CardapioItem.idorditem).all()
        saida.append({"cardapioversaocategoria_id": vinculo.cardapioversaocategoria_id, "categoria_id": categoria.categoria_id, "nmcategoria": categoria.nmcategoria, "dsicone": categoria.dsicone, "idordcategoria": vinculo.idordcategoria, "itens": [{"cardapioitem_id": ci.cardapioitem_id, "produto_id": p.produto_id, "organizacao_id": p.organizacao_id, "loja_id": p.loja_id, "categoria_id": categoria.categoria_id, "nmcategoria": categoria.nmcategoria, "nmproduto": p.nmproduto, "dsproduto": p.dsproduto, "urlfotoproduto": p.urlfotoproduto, "vrpreco": float(ci.vrpreco), "vrprecoprod": float(ci.vrpreco), "vrprecofinal": float(ci.vrpreco), "sitproduto": p.sitproduto, "tipodesconto": "NENHUM", "vrdesconto": 0.0, "descontoativo": False, "pccashback": float(p.pccashback) if p.pccashback is not None else None, "idorditem": ci.idorditem} for ci, p in itens]})
    return {"cardapio_id": cardapio.cardapio_id, "nmcardapio": cardapio.nmcardapio, "cardapioversao_id": versao.cardapioversao_id, "nrversao": versao.nrversao, "statusversao": versao.statusversao, "categorias": saida}


@router.get("/lojas/{loja_id}/cardapios")
def listar(loja_id: int, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    _loja(db, loja_id, payload)
    return [_saida_cardapio(db, item) for item in db.query(Cardapio).filter(Cardapio.loja_id == loja_id).order_by(Cardapio.prioridade.desc(), Cardapio.nmcardapio).all()]


@router.post("/lojas/{loja_id}/cardapios", status_code=201)
def criar(loja_id: int, dados: CardapioIn, payload=Depends(get_usuario_logado), db: Session=Depends(get_db)):
    loja = _loja(db, loja_id, payload)
    tipo = dados.tipocardapio.upper()
    if tipo not in {"PRINCIPAL", "ESPECIAL", "SAZONAL", "EVENTO"}:
        raise HTTPException(422, "Tipo de cardápio inválido.")
    if tipo == "PRINCIPAL" and db.query(Cardapio).filter(Cardapio.loja_id == loja_id, Cardapio.tipocardapio == "PRINCIPAL", Cardapio.sitcardapio == "ATIVO").first():
        raise HTTPException(409, "A loja já possui um cardápio principal.")
    item = Cardapio(organizacao_id=loja.organizacao_id, loja_id=loja_id, nmcardapio=dados.nmcardapio.strip(), tipocardapio=tipo, prioridade=dados.prioridade)
    db.add(item); db.flush()
    db.add(CardapioVersao(cardapio_id=item.cardapio_id, nrversao=1))
    db.commit(); db.refresh(item)
    return _saida_cardapio(db, item)


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
    if db.query(Produto).filter(Produto.produto_id.in_(produtos_ids), Produto.loja_id == cardapio.loja_id, Produto.idtipoproduto == "P").count() != len(produtos_ids):
        raise HTTPException(422, "Um ou mais produtos não pertencem à loja.")
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
    try:
        validar_publicacao_loja(db, cardapio.loja_id)
    except HTTPException:
        if not dados.publicar_apos_aprovacao:
            raise
        versao.statusversao, versao.publicaraposaprovacao = "AGUARDANDO_ASAAS", "S"
        db.commit()
        return {"statusversao": versao.statusversao, "mensagem": "Cardápio será publicado após a aprovação do Asaas."}
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
