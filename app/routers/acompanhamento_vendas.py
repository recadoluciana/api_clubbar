from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventosetor import EventoSetor
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.produto import Produto
from app.models.venda import Venda


router = APIRouter(prefix="/acompanhamento-vendas", tags=["Acompanhamento de vendas"])
_CARGOS = {"SUPERADMIN", "ADMIN", "GERENTE"}
_FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def _escopo(usuario: dict) -> tuple[int, int | None]:
    if usuario.get("role") != "usuario" and usuario.get("tipo") != "usuario":
        raise HTTPException(403, "Acesso permitido apenas a usuários parceiros")
    try:
        organizacao_id = int(usuario.get("organizacao_id") or 0)
    except (TypeError, ValueError):
        organizacao_id = 0
    cargo = str(usuario.get("dscargo") or "").upper()
    if organizacao_id <= 0 or cargo not in _CARGOS:
        raise HTTPException(403, "Usuário sem permissão para acompanhar vendas")
    if cargo == "GERENTE":
        try:
            loja_id = int(usuario.get("loja_id") or 0)
        except (TypeError, ValueError):
            loja_id = 0
        if loja_id <= 0:
            raise HTTPException(403, "Gerente sem estabelecimento vinculado")
        return organizacao_id, loja_id
    return organizacao_id, None


def _dinheiro(valor) -> float:
    return float(Decimal(str(valor or 0)).quantize(Decimal("0.01")))


def _validar_loja(db: Session, organizacao_id: int, loja_escopo: int | None, loja_id: int | None):
    if loja_escopo is not None and loja_id not in (None, loja_escopo):
        raise HTTPException(403, "Estabelecimento fora do escopo do usuário")
    if loja_id is not None and not db.query(Loja.loja_id).filter(
        Loja.loja_id == loja_id, Loja.organizacao_id == organizacao_id
    ).first():
        raise HTTPException(404, "Estabelecimento não encontrado")


@router.get("/produtos-pendentes")
def produtos_pendentes(
    loja_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    organizacao_id, loja_escopo = _escopo(usuario)
    _validar_loja(db, organizacao_id, loja_escopo, loja_id)
    loja_final = loja_escopo or loja_id
    quantidade = func.coalesce(func.sum(case((Venda.venda_id.isnot(None), ItVenda.qtitvenda), else_=0)), 0)
    valor = func.coalesce(func.sum(case((Venda.venda_id.isnot(None), ItVenda.qtitvenda * ItVenda.vrunititvenda), else_=0)), 0)
    query = db.query(
        Loja.loja_id,
        Loja.nmloja,
        Produto.produto_id,
        Produto.nmproduto,
        Produto.urlfotoproduto,
        quantidade.label("quantidade"),
        valor.label("valor"),
    ).join(Venda, Venda.loja_id == Loja.loja_id).join(
        ItVenda, ItVenda.venda_id == Venda.venda_id
    ).join(Produto, Produto.produto_id == ItVenda.produto_id).filter(
        Venda.organizacao_id == organizacao_id,
        Venda.sitvenda == "PAGA",
        ItVenda.tipoitem == "PRODUTO",
        ItVenda.sititvenda == "ATIVO",
        ItVenda.identregaitvenda == "NAO",
        Produto.idtipoproduto == "P",
    )
    if loja_final is not None:
        query = query.filter(Venda.loja_id == loja_final)
    rows = query.group_by(
        Loja.loja_id, Loja.nmloja, Produto.produto_id,
        Produto.nmproduto, Produto.urlfotoproduto,
    ).order_by(Loja.nmloja, quantidade.desc(), Produto.nmproduto).all()
    itens = [{
        "loja_id": int(row.loja_id), "nmloja": row.nmloja,
        "produto_id": int(row.produto_id), "nmproduto": row.nmproduto,
        "urlfotoproduto": row.urlfotoproduto,
        "quantidade_pendente": int(row.quantidade or 0),
        "valor_total": _dinheiro(row.valor),
    } for row in rows]
    return {
        "quantidade_total": sum(item["quantidade_pendente"] for item in itens),
        "valor_total": _dinheiro(sum(Decimal(str(item["valor_total"])) for item in itens)),
        "itens": itens,
    }


@router.get("/eventos")
def eventos_vendas(
    periodo: str = Query(default="FUTUROS", pattern="^(FUTUROS|REALIZADOS|TODOS)$"),
    loja_id: int | None = Query(default=None, ge=1),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    organizacao_id, loja_escopo = _escopo(usuario)
    _validar_loja(db, organizacao_id, loja_escopo, loja_id)
    loja_final = loja_escopo or loja_id
    quantidade = func.coalesce(func.sum(case((Venda.venda_id.isnot(None), ItVenda.qtitvenda), else_=0)), 0)
    valor = func.coalesce(func.sum(case((Venda.venda_id.isnot(None), ItVenda.qtitvenda * ItVenda.vrunititvenda), else_=0)), 0)
    query = db.query(
        Evento.evento_id, Evento.nmtituloevento, Evento.dtinicioevento,
        Evento.urlbannerevento, Evento.statusevento, Loja.nmloja,
        quantidade.label("quantidade"), valor.label("valor"),
    ).join(Loja, Loja.loja_id == Evento.loja_id).outerjoin(
        EventoLote, EventoLote.evento_id == Evento.evento_id
    ).outerjoin(ItVenda, (ItVenda.lote_id == EventoLote.lote_id) & (ItVenda.sititvenda == "ATIVO")).outerjoin(
        Venda, (Venda.venda_id == ItVenda.venda_id) & (Venda.sitvenda == "PAGA")
    ).filter(Evento.organizacao_id == organizacao_id)
    if loja_final is not None:
        query = query.filter(Evento.loja_id == loja_final)
    agora = datetime.now(_FUSO_BRASIL).replace(tzinfo=None)
    if periodo == "FUTUROS":
        query = query.filter(Evento.dtinicioevento >= agora)
    elif periodo == "REALIZADOS":
        query = query.filter(Evento.dtinicioevento < agora)
    rows = query.group_by(
        Evento.evento_id, Evento.nmtituloevento, Evento.dtinicioevento,
        Evento.urlbannerevento, Evento.statusevento, Loja.nmloja,
    ).order_by(Evento.dtinicioevento.desc() if periodo == "REALIZADOS" else Evento.dtinicioevento.asc()).all()
    return [{
        "evento_id": int(row.evento_id), "nmtituloevento": row.nmtituloevento,
        "dtinicioevento": row.dtinicioevento, "urlbannerevento": row.urlbannerevento,
        "statusevento": row.statusevento, "nmloja": row.nmloja,
        "quantidade_vendida": int(row.quantidade or 0), "valor_total": _dinheiro(row.valor),
    } for row in rows]


@router.get("/eventos/{evento_id}")
def detalhe_vendas_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    organizacao_id, loja_escopo = _escopo(usuario)
    evento = db.query(Evento).filter(
        Evento.evento_id == evento_id, Evento.organizacao_id == organizacao_id
    ).first()
    if not evento or (loja_escopo is not None and evento.loja_id != loja_escopo):
        raise HTTPException(404, "Evento não encontrado")
    quantidade = func.coalesce(func.sum(case((Venda.venda_id.isnot(None), ItVenda.qtitvenda), else_=0)), 0)
    valor = func.coalesce(func.sum(case((Venda.venda_id.isnot(None), ItVenda.qtitvenda * ItVenda.vrunititvenda), else_=0)), 0)
    rows = db.query(
        EventoLote.lote_id, EventoLote.nrlote, EventoLote.nmlote,
        EventoLote.tipoingresso, EventoLote.vrprecolote,
        EventoSetor.nmsetor, quantidade.label("quantidade"), valor.label("valor"),
    ).outerjoin(EventoSetor, EventoSetor.eventosetor_id == EventoLote.eventosetor_id).outerjoin(
        ItVenda, (ItVenda.lote_id == EventoLote.lote_id) & (ItVenda.sititvenda == "ATIVO")
    ).outerjoin(Venda, (Venda.venda_id == ItVenda.venda_id) & (Venda.sitvenda == "PAGA")).filter(
        EventoLote.evento_id == evento_id
    ).group_by(
        EventoLote.lote_id, EventoLote.nrlote, EventoLote.nmlote,
        EventoLote.tipoingresso, EventoLote.vrprecolote, EventoSetor.nmsetor,
    ).order_by(EventoLote.nrlote, EventoSetor.nmsetor, EventoLote.tipoingresso).all()
    lotes = [{
        "lote_id": int(row.lote_id), "nrlote": int(row.nrlote), "nmlote": row.nmlote,
        "setor": row.nmsetor or "Setor único", "tipo": row.tipoingresso,
        "valor_unitario": _dinheiro(row.vrprecolote),
        "quantidade_vendida": int(row.quantidade or 0), "valor_total": _dinheiro(row.valor),
    } for row in rows]
    return {
        "evento_id": evento.evento_id, "nmtituloevento": evento.nmtituloevento,
        "dtinicioevento": evento.dtinicioevento,
        "quantidade_vendida": sum(item["quantidade_vendida"] for item in lotes),
        "valor_total": _dinheiro(sum(Decimal(str(item["valor_total"])) for item in lotes)),
        "lotes": lotes,
    }
