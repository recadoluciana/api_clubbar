from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cliente import Cliente
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventoloteglobal import EventoLoteGlobal
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.pagvenda import PagVenda
from app.models.produto import Produto
from app.models.venda import Venda


router = APIRouter(prefix="/acompanhamento-vendas", tags=["Acompanhamento de vendas"])
_CARGOS = {"SUPERADMIN", "ADMIN", "MANAGER"}
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
    if cargo == "MANAGER":
        try:
            loja_id = int(usuario.get("loja_id") or 0)
        except (TypeError, ValueError):
            loja_id = 0
        if loja_id <= 0:
            raise HTTPException(403, "Manager sem estabelecimento vinculado")
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


@router.get("/produtos")
def listar_compras_produtos(
    situacao: str = Query(default="TODOS", pattern="^(TODOS|PENDENTES|RETIRADOS)$"),
    loja_id: int | None = Query(default=None, ge=1),
    limite: int = Query(default=500, ge=1, le=1000),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Lista compras pagas de produtos e sua situação de retirada.

    O resultado é deliberadamente detalhado por item de venda: assim o
    parceiro consegue identificar o cliente, o produto comprado e a baixa
    realizada na portaria ou no balcão, sem misturar itens já retirados aos
    que ainda estão na carteira.
    """
    organizacao_id, loja_escopo = _escopo(usuario)
    _validar_loja(db, organizacao_id, loja_escopo, loja_id)
    loja_final = loja_escopo or loja_id

    query = (
        db.query(
            ItVenda.itvenda_id,
            ItVenda.qtitvenda,
            ItVenda.vrunititvenda,
            ItVenda.identregaitvenda,
            ItVenda.dtentregaitvenda,
            ItVenda.nmuserentregaitvenda,
            Venda.venda_id,
            Venda.dtcriacao.label("dtcompra"),
            Loja.loja_id,
            Loja.nmloja,
            Cliente.cliente_id,
            Cliente.nmcliente,
            Cliente.emailcliente,
            Produto.produto_id,
            Produto.nmproduto,
            Produto.urlfotoproduto,
        )
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Loja, Loja.loja_id == Venda.loja_id)
        .outerjoin(Cliente, Cliente.cliente_id == Venda.cliente_id)
        .join(Produto, Produto.produto_id == ItVenda.produto_id)
        .filter(
            Venda.organizacao_id == organizacao_id,
            Venda.sitvenda == "PAGA",
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.sititvenda == "ATIVO",
        )
    )
    if loja_final is not None:
        query = query.filter(Venda.loja_id == loja_final)
    if situacao == "PENDENTES":
        query = query.filter(ItVenda.identregaitvenda != "SIM")
    elif situacao == "RETIRADOS":
        query = query.filter(ItVenda.identregaitvenda == "SIM")

    rows = (
        query.order_by(Venda.dtcriacao.desc(), ItVenda.itvenda_id.desc())
        .limit(limite)
        .all()
    )
    itens = []
    for row in rows:
        retirado = (row.identregaitvenda or "NAO").upper() == "SIM"
        quantidade = int(row.qtitvenda or 0)
        preco_unitario = _dinheiro(row.vrunititvenda)
        itens.append(
            {
                "itvenda_id": int(row.itvenda_id),
                "venda_id": int(row.venda_id),
                "loja_id": int(row.loja_id),
                "nmloja": row.nmloja,
                "cliente_id": int(row.cliente_id) if row.cliente_id else None,
                "nmcliente": row.nmcliente or "Cliente não identificado",
                "emailcliente": row.emailcliente or "",
                "produto_id": int(row.produto_id),
                "nmproduto": row.nmproduto,
                "urlfotoproduto": row.urlfotoproduto or "",
                "quantidade": quantidade,
                "preco_unitario": preco_unitario,
                "valor_total": _dinheiro(Decimal(str(row.vrunititvenda or 0)) * quantidade),
                "dtcompra": row.dtcompra,
                "retirado": retirado,
                "dtretirada": row.dtentregaitvenda,
                "responsavel_retirada": row.nmuserentregaitvenda or "",
                "cortesia": Decimal(str(row.vrunititvenda or 0)) <= 0,
            }
        )
    return {"itens": itens, "limite": limite}


def _valor_enum(valor):
    return getattr(valor, "value", valor)


@router.get("/clientes")
def listar_clientes_com_compras(
    busca: str | None = Query(default=None, max_length=160),
    limite: int = Query(default=1000, ge=1, le=2000),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Lista os clientes que já compraram na organização e seus históricos.

    A tabela ``cliente`` é global na plataforma. Por isso, o Partner só recebe
    clientes associados a vendas da própria organização (ou da própria loja,
    quando o usuário é MANAGER). Dados de autenticação e links de pagamento
    não são devolvidos deliberadamente.
    """
    organizacao_id, loja_escopo = _escopo(usuario)

    consulta_clientes = (
        db.query(Cliente)
        .join(Venda, Venda.cliente_id == Cliente.cliente_id)
        .filter(Venda.organizacao_id == organizacao_id)
    )
    if loja_escopo is not None:
        consulta_clientes = consulta_clientes.filter(Venda.loja_id == loja_escopo)

    termo = (busca or "").strip()
    if termo:
        padrao = f"%{termo}%"
        consulta_clientes = consulta_clientes.filter(
            or_(
                Cliente.nmcliente.ilike(padrao),
                Cliente.emailcliente.ilike(padrao),
                Cliente.nrtelcliente.ilike(padrao),
                Cliente.nrcpfcliente.ilike(padrao),
            )
        )

    clientes = (
        consulta_clientes.distinct()
        .order_by(Cliente.nmcliente.asc(), Cliente.cliente_id.asc())
        .limit(limite)
        .all()
    )
    cliente_ids = [int(cliente.cliente_id) for cliente in clientes]
    if not cliente_ids:
        return {"clientes": [], "total_clientes": 0, "limite": limite}

    consulta_vendas = (
        db.query(Venda, Loja.nmloja)
        .join(Loja, Loja.loja_id == Venda.loja_id)
        .filter(
            Venda.organizacao_id == organizacao_id,
            Venda.cliente_id.in_(cliente_ids),
        )
    )
    if loja_escopo is not None:
        consulta_vendas = consulta_vendas.filter(Venda.loja_id == loja_escopo)
    vendas_linhas = consulta_vendas.order_by(
        Venda.dtcriacao.desc(), Venda.venda_id.desc()
    ).all()
    venda_ids = [int(venda.venda_id) for venda, _ in vendas_linhas]

    itens_por_venda: dict[int, list[dict]] = {venda_id: [] for venda_id in venda_ids}
    pagamentos_por_venda: dict[int, list[dict]] = {
        venda_id: [] for venda_id in venda_ids
    }
    if venda_ids:
        itens = (
            db.query(ItVenda, Produto.nmproduto)
            .outerjoin(Produto, Produto.produto_id == ItVenda.produto_id)
            .filter(ItVenda.venda_id.in_(venda_ids))
            .order_by(ItVenda.venda_id.asc(), ItVenda.itvenda_id.asc())
            .all()
        )
        for item, nmproduto in itens:
            itens_por_venda[int(item.venda_id)].append(
                {
                    "itvenda_id": int(item.itvenda_id),
                    "tipoitem": _valor_enum(item.tipoitem),
                    "produto_id": int(item.produto_id) if item.produto_id else None,
                    "nmproduto": nmproduto or "",
                    "cardapioitem_id": int(item.cardapioitem_id)
                    if item.cardapioitem_id
                    else None,
                    "qtitvenda": int(item.qtitvenda or 0),
                    "vrunititvenda": _dinheiro(item.vrunititvenda),
                    "identregaitvenda": _valor_enum(item.identregaitvenda),
                    "dtentregaitvenda": item.dtentregaitvenda,
                    "idcontrolebar": _valor_enum(item.idcontrolebar),
                    "nrmesa": item.nrmesa or "",
                    "userentregaitvenda": int(item.userentregaitvenda)
                    if item.userentregaitvenda
                    else None,
                    "nmuserentregaitvenda": item.nmuserentregaitvenda or "",
                    "dsobsitvenda": item.dsobsitvenda or "",
                    "dtcriacao": item.dtcriacao,
                    "dtexpiraitvenda": item.dtexpiraitvenda,
                    "nmparticipante": item.nmparticipante or "",
                    "cpfparticipante": item.cpfparticipante or "",
                    "lote_id": int(item.lote_id) if item.lote_id else None,
                    "lotepreco_id": int(item.lotepreco_id)
                    if item.lotepreco_id
                    else None,
                    "modalidade_id": int(item.modalidade_id)
                    if item.modalidade_id
                    else None,
                    "beneficio_id": int(item.beneficio_id)
                    if item.beneficio_id
                    else None,
                    "tipobeneficio": item.tipobeneficio or "",
                    "nmmodalidadesnapshot": item.nmmodalidadesnapshot or "",
                    "nmbeneficiosnapshot": item.nmbeneficiosnapshot or "",
                    "pctaxaitvenda": _dinheiro(item.pctaxaitvenda),
                    "vrtaxaitvenda": _dinheiro(item.vrtaxaitvenda),
                    "sititvenda": _valor_enum(item.sititvenda),
                    "dtcancelamento": item.dtcancelamento,
                    "vrreembolso": _dinheiro(item.vrreembolso),
                    "idreembolso": item.idreembolso or "",
                    "dtultatu": item.dtultatu,
                }
            )

        pagamentos = (
            db.query(PagVenda)
            .filter(PagVenda.venda_id.in_(venda_ids))
            .order_by(PagVenda.venda_id.asc(), PagVenda.pagvenda_id.asc())
            .all()
        )
        for pagamento in pagamentos:
            pagamentos_por_venda[int(pagamento.venda_id)].append(
                {
                    "pagvenda_id": int(pagamento.pagvenda_id),
                    "dsmetodopag": pagamento.dsmetodopag,
                    "vrpagvenda": _dinheiro(pagamento.vrpagvenda),
                    "sitpagvenda": _valor_enum(pagamento.sitpagvenda),
                    "idtransacaopagvenda": pagamento.idtransacaopagvenda or "",
                    "dtconftranspagvenda": pagamento.dtconftranspagvenda,
                    "provedor": pagamento.provedor or "",
                    "reference_id": pagamento.reference_id or "",
                    "checkout_id": pagamento.checkout_id or "",
                    "dtcriacao": pagamento.dtcriacao,
                }
            )

    compras_por_cliente: dict[int, list[dict]] = {
        cliente_id: [] for cliente_id in cliente_ids
    }
    for venda, nmloja in vendas_linhas:
        venda_id = int(venda.venda_id)
        compras_por_cliente[int(venda.cliente_id)].append(
            {
                "venda_id": venda_id,
                "organizacao_id": int(venda.organizacao_id),
                "loja_id": int(venda.loja_id),
                "nmloja": nmloja,
                "carrinho_id": int(venda.carrinho_id) if venda.carrinho_id else None,
                "reserva_ingresso_id": int(venda.reserva_ingresso_id)
                if venda.reserva_ingresso_id
                else None,
                "usuario_id": int(venda.usuario_id) if venda.usuario_id else None,
                "tipovenda": _valor_enum(venda.tipovenda),
                "dsplataforma": _valor_enum(venda.dsplataforma),
                "sitvenda": _valor_enum(venda.sitvenda),
                "totalvenda": _dinheiro(venda.totalvenda),
                "dtcriacao": venda.dtcriacao,
                "dtultatu": venda.dtultatu,
                "itens": itens_por_venda[venda_id],
                "pagamentos": pagamentos_por_venda[venda_id],
            }
        )

    resposta = []
    for cliente in clientes:
        cliente_id = int(cliente.cliente_id)
        compras = compras_por_cliente[cliente_id]
        resposta.append(
            {
                "cliente": {
                    "cliente_id": cliente_id,
                    "nmcliente": cliente.nmcliente,
                    "emailcliente": cliente.emailcliente,
                    "sitcliente": cliente.sitcliente,
                    "emailconf": cliente.emailconf,
                    "dtcriacao": cliente.dtcriacao,
                    "cliente_padrao": cliente.cliente_padrao,
                    "dtultatu": cliente.dtultatu,
                    "nrtelcliente": cliente.nrtelcliente or "",
                    "nrcpfcliente": cliente.nrcpfcliente or "",
                    "idclienteasaas": cliente.idclienteasaas or "",
                    "endcliente": cliente.endcliente or "",
                    "nrendcliente": cliente.nrendcliente or "",
                    "complcliente": cliente.complcliente or "",
                    "bairrocliente": cliente.bairrocliente or "",
                    "cepcliente": cliente.cepcliente or "",
                    "cidadecliente": cliente.cidadecliente or "",
                    "ufcliente": cliente.ufcliente or "",
                    "idcidadeibge": int(cliente.idcidadeibge)
                    if cliente.idcidadeibge
                    else None,
                },
                "resumo": {
                    "quantidade_compras": len(compras),
                    "valor_total_compras": _dinheiro(
                        sum(Decimal(str(compra["totalvenda"])) for compra in compras)
                    ),
                    "ultima_compra": compras[0]["dtcriacao"] if compras else None,
                },
                "compras": compras,
            }
        )
    return {"clientes": resposta, "total_clientes": len(resposta), "limite": limite}


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

    quantidade_pendente = int(
        db.query(func.coalesce(func.sum(ItVenda.qtitvenda), 0))
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .filter(
            EventoLote.evento_id == evento.evento_id,
            Venda.sitvenda == "PAGA",
            ItVenda.tipoitem == "INGRESSO",
            ItVenda.sititvenda == "ATIVO",
            or_(
                ItVenda.identregaitvenda.is_(None),
                ItVenda.identregaitvenda != "SIM",
            ),
        )
        .scalar()
        or 0
    )
    quantidade = func.coalesce(func.sum(case((Venda.venda_id.isnot(None), ItVenda.qtitvenda), else_=0)), 0)
    valor = func.coalesce(func.sum(case((Venda.venda_id.isnot(None), ItVenda.qtitvenda * ItVenda.vrunititvenda), else_=0)), 0)
    rows = db.query(
        EventoLote.lote_id, EventoLote.nrlote, EventoLote.nmlote,
        EventoLote.qttotallote, EventoLote.usarcapacidaderestante,
        EventoLote.eventosetor_id,
        EventoLotePreco.tipopreco, EventoLotePreco.vrpreco,
        EventoSetor.nmsetor, EventoSetor.qtcapacidade,
        quantidade.label("quantidade"), valor.label("valor"),
    ).join(EventoLotePreco, EventoLotePreco.lote_id == EventoLote.lote_id).outerjoin(EventoSetor, EventoSetor.eventosetor_id == EventoLote.eventosetor_id).outerjoin(
        ItVenda, (ItVenda.lotepreco_id == EventoLotePreco.lotepreco_id) & (ItVenda.sititvenda == "ATIVO")
    ).outerjoin(Venda, (Venda.venda_id == ItVenda.venda_id) & (Venda.sitvenda == "PAGA")).filter(
        EventoLote.evento_id == evento_id
    ).group_by(
        EventoLote.lote_id, EventoLote.nrlote, EventoLote.nmlote,
        EventoLote.qttotallote, EventoLote.usarcapacidaderestante,
        EventoLote.eventosetor_id,
        EventoLotePreco.tipopreco, EventoLotePreco.vrpreco,
        EventoSetor.nmsetor, EventoSetor.qtcapacidade,
    ).order_by(EventoLote.nrlote, EventoSetor.nmsetor, EventoLotePreco.nrordem).all()

    vendidos_por_lote: dict[int, int] = {}
    vendidos_por_setor: dict[int, int] = {}
    for row in rows:
        lote_id = int(row.lote_id)
        vendidos_por_lote[lote_id] = (
            vendidos_por_lote.get(lote_id, 0) + int(row.quantidade or 0)
        )
        if row.eventosetor_id is not None:
            setor_id = int(row.eventosetor_id)
            vendidos_por_setor[setor_id] = (
                vendidos_por_setor.get(setor_id, 0) + int(row.quantidade or 0)
            )

    capacidade_total = int(
        db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0)).filter(
            EventoSetor.evento_id == evento_id,
            EventoSetor.sitsetor == "ATIVO",
        ).scalar()
        or 0
    )

    def _capacidade_e_restante(row) -> tuple[int | None, int | None]:
        vendidos_lote = vendidos_por_lote.get(int(row.lote_id), 0)
        if row.qttotallote is not None:
            capacidade = int(row.qttotallote)
            return capacidade, max(capacidade - vendidos_lote, 0)
        if row.eventosetor_id is not None and row.qtcapacidade is not None:
            setor_id = int(row.eventosetor_id)
            restante = max(
                int(row.qtcapacidade) - vendidos_por_setor.get(setor_id, 0), 0
            )
            return vendidos_lote + restante, restante
        return None, None

    lotes = []
    for row in rows:
        capacidade_lote, quantidade_restante = _capacidade_e_restante(row)
        lotes.append({
            "lote_id": int(row.lote_id), "nrlote": int(row.nrlote),
            "nmlote": row.nmlote, "setor": row.nmsetor or "Setor único",
            "tipo": row.tipopreco, "valor_unitario": _dinheiro(row.vrpreco),
            "quantidade_vendida": int(row.quantidade or 0),
            "quantidade_vendida_lote": vendidos_por_lote.get(int(row.lote_id), 0),
            "capacidade_lote": capacidade_lote,
            "quantidade_restante": quantidade_restante,
            "valor_total": _dinheiro(row.valor),
        })
    quantidade_total = sum(item["quantidade_vendida"] for item in lotes)
    quantidade_restante = max(capacidade_total - quantidade_total, 0)
    percentual_ocupacao = (
        round(min(quantidade_total / capacidade_total * 100, 100), 2)
        if capacidade_total > 0 else 0.0
    )
    return {
        "evento_id": evento.evento_id, "nmtituloevento": evento.nmtituloevento,
        "dtinicioevento": evento.dtinicioevento,
        "quantidade_vendida": quantidade_total,
        "quantidade_pendente": quantidade_pendente,
        "capacidade_total": capacidade_total,
        "quantidade_restante": quantidade_restante,
        "percentual_ocupacao": percentual_ocupacao,
        "valor_total": _dinheiro(sum(Decimal(str(item["valor_total"])) for item in lotes)),
        "lotes": lotes,
    }


@router.get("/eventos/{evento_id}/ingressos")
def listar_ingressos_vendidos_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Lista os ingressos efetivamente vendidos, preservando o preço da compra."""
    organizacao_id, loja_escopo = _escopo(usuario)
    evento = db.query(Evento).filter(
        Evento.evento_id == evento_id,
        Evento.organizacao_id == organizacao_id,
    ).first()
    if not evento or (loja_escopo is not None and evento.loja_id != loja_escopo):
        raise HTTPException(404, "Evento não encontrado")

    rows = (
        db.query(
            ItVenda.itvenda_id,
            ItVenda.qtitvenda,
            ItVenda.vrunititvenda,
            ItVenda.vrtaxaitvenda,
            ItVenda.identregaitvenda,
            ItVenda.dtentregaitvenda,
            ItVenda.nmparticipante,
            ItVenda.cpfparticipante,
            ItVenda.nmmodalidadesnapshot,
            Venda.venda_id,
            Venda.dtcriacao.label("dtcompra"),
            Cliente.nmcliente,
            Cliente.nrtelcliente,
            EventoLoteGlobal.nrlote,
            EventoLoteGlobal.nmlote,
            EventoSetor.nmsetor,
            EventoLotePreco.nmpreco,
            EventoLotePreco.tipopreco,
        )
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .outerjoin(Cliente, Cliente.cliente_id == Venda.cliente_id)
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .join(
            EventoLoteGlobal,
            EventoLoteGlobal.loteglobal_id == EventoLote.loteglobal_id,
        )
        .outerjoin(
            EventoSetor,
            EventoSetor.eventosetor_id == EventoLote.eventosetor_id,
        )
        .outerjoin(
            EventoLotePreco,
            EventoLotePreco.lotepreco_id == ItVenda.lotepreco_id,
        )
        .filter(
            EventoLoteGlobal.evento_id == evento.evento_id,
            Venda.sitvenda == "PAGA",
            ItVenda.tipoitem == "INGRESSO",
            ItVenda.sititvenda == "ATIVO",
        )
        .order_by(Venda.dtcriacao.desc(), ItVenda.itvenda_id.desc())
        .all()
    )

    return [
        {
            "itvenda_id": int(row.itvenda_id),
            "quantidade": int(row.qtitvenda or 0),
            "preco": _dinheiro(row.vrunititvenda),
            "taxa": _dinheiro(row.vrtaxaitvenda),
            "venda_id": int(row.venda_id),
            "dtcompra": row.dtcompra,
            "cliente": row.nmcliente or "Cliente não identificado",
            "telefone_cliente": row.nrtelcliente or "",
            "participante": row.nmparticipante or "Não informado",
            "cpf_participante": row.cpfparticipante or "",
            "numero_lote": int(row.nrlote),
            "lote": row.nmlote or "Lote não informado",
            "setor": row.nmsetor or "Setor único",
            "modalidade": (
                row.nmmodalidadesnapshot
                or row.nmpreco
                or row.tipopreco
                or "Ingresso"
            ),
            "utilizado": (row.identregaitvenda or "NAO").upper() == "SIM",
            "dtvalidacao": row.dtentregaitvenda,
        }
        for row in rows
    ]
