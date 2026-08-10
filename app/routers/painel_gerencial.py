from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.produto import Produto
from app.models.venda import Venda
from app.schemas.painel_gerencial import PainelGerencialOut


router = APIRouter(tags=["Painel gerencial"])
_CARGOS_GERENCIAL = {"SUPERADMIN", "ADMIN"}
_FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def _hoje_local() -> date:
    return datetime.now(_FUSO_BRASIL).date()


def _inicio_local_em_utc_naive(data_local: date) -> datetime:
    return datetime.combine(data_local, time.min, tzinfo=_FUSO_BRASIL).astimezone(
        timezone.utc
    ).replace(tzinfo=None)


def _inteiro_positivo(valor: object, nome: str) -> int:
    try:
        convertido = int(valor)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise HTTPException(status_code=403, detail=f"Token sem {nome} válido")
    if convertido <= 0:
        raise HTTPException(status_code=403, detail=f"Token sem {nome} válido")
    return convertido


def _extrair_escopo(usuario: dict) -> tuple[int, int | None]:
    if usuario.get("role") != "usuario" and usuario.get("tipo") != "usuario":
        raise HTTPException(status_code=403, detail="Acesso permitido apenas a usuários parceiros")

    organizacao_id = _inteiro_positivo(usuario.get("organizacao_id"), "organizacao_id")
    cargo = str(usuario.get("dscargo") or "").strip().upper()

    if cargo not in _CARGOS_GERENCIAL:
        raise HTTPException(
            status_code=403,
            detail="O painel gerencial é exclusivo para SUPERADMIN e ADMIN",
        )

    # O painel gerencial é sempre consolidado para toda a organização,
    # inclusive quando o administrador possui uma loja vinculada.
    return organizacao_id, None


def _dinheiro(valor: object) -> float:
    return float(round(Decimal(str(valor or 0)), 2))


@router.get("/painel-gerencial", response_model=PainelGerencialOut)
def painel_gerencial(
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    organizacao_id, loja_id = _extrair_escopo(usuario)

    hoje = _hoje_local()
    primeiro_dia = hoje.replace(day=1)
    inicio_mes = _inicio_local_em_utc_naive(primeiro_dia)
    inicio_hoje = _inicio_local_em_utc_naive(hoje)
    fim_exclusivo = _inicio_local_em_utc_naive(hoje + timedelta(days=1))

    lojas_query = db.query(Loja.loja_id, Loja.nmloja).filter(
        Loja.organizacao_id == organizacao_id
    )
    if loja_id is not None:
        lojas_query = lojas_query.filter(Loja.loja_id == loja_id)

    lojas = lojas_query.order_by(Loja.nmloja, Loja.loja_id).all()
    if loja_id is not None and not lojas:
        raise HTTPException(status_code=403, detail="Loja não pertence à organização do usuário")

    filtros_mes = [
        Venda.organizacao_id == organizacao_id,
        Venda.sitvenda == "PAGA",
        Venda.dtcriacao >= inicio_mes,
        Venda.dtcriacao < fim_exclusivo,
    ]
    if loja_id is not None:
        filtros_mes.append(Venda.loja_id == loja_id)

    resumo = db.query(
        func.coalesce(func.sum(Venda.totalvenda), 0).label("total_mes"),
        func.count(Venda.venda_id).label("pedidos_mes"),
    ).filter(*filtros_mes).one()

    filtros_hoje = [
        Venda.organizacao_id == organizacao_id,
        Venda.sitvenda == "PAGA",
        Venda.dtcriacao >= inicio_hoje,
        Venda.dtcriacao < fim_exclusivo,
    ]
    if loja_id is not None:
        filtros_hoje.append(Venda.loja_id == loja_id)

    total_hoje = db.query(
        func.coalesce(func.sum(Venda.totalvenda), 0)
    ).filter(*filtros_hoje).scalar()

    ingressos_vendidos = db.query(
        func.coalesce(func.sum(ItVenda.qtitvenda), 0)
    ).join(Venda, Venda.venda_id == ItVenda.venda_id).filter(
        *filtros_mes,
        ItVenda.lote_id.isnot(None),
    ).scalar()

    participacao_rows = db.query(
        Venda.loja_id,
        func.coalesce(func.sum(Venda.totalvenda), 0).label("valor"),
    ).filter(*filtros_mes).group_by(Venda.loja_id).all()
    valores_por_loja = {int(row.loja_id): _dinheiro(row.valor) for row in participacao_rows}
    total_mes = _dinheiro(resumo.total_mes)

    participacao_lojas = []
    for loja in lojas:
        valor = valores_por_loja.get(int(loja.loja_id), 0.0)
        percentual = round((valor / total_mes) * 100, 2) if total_mes else 0.0
        participacao_lojas.append({
            "loja_id": int(loja.loja_id),
            "nmloja": loja.nmloja,
            "valor": valor,
            "percentual": percentual,
        })

    quantidade_produto = func.sum(ItVenda.qtitvenda).label("quantidade")
    valor_produto = func.sum(ItVenda.qtitvenda * ItVenda.vrunititvenda).label("valor")
    produtos_query = db.query(
        Produto.produto_id,
        Produto.nmproduto.label("nome"),
        quantidade_produto,
        valor_produto,
    ).join(ItVenda, ItVenda.produto_id == Produto.produto_id).join(
        Venda, Venda.venda_id == ItVenda.venda_id
    ).filter(
        *filtros_mes,
        Produto.organizacao_id == organizacao_id,
        Produto.idtipoproduto == "P",
        ItVenda.lote_id.is_(None),
    )
    if loja_id is not None:
        produtos_query = produtos_query.filter(Produto.loja_id == loja_id)
    produtos_rows = produtos_query.group_by(
        Produto.produto_id, Produto.nmproduto
    ).order_by(quantidade_produto.desc(), Produto.nmproduto).all()

    quantidade_ingresso = func.sum(ItVenda.qtitvenda).label("quantidade")
    valor_ingresso = func.sum(ItVenda.qtitvenda * ItVenda.vrunititvenda).label("valor")
    ingressos_query = db.query(
        EventoLote.lote_id,
        Evento.nmtituloevento,
        EventoLote.nmlote,
        quantidade_ingresso,
        valor_ingresso,
    ).join(ItVenda, ItVenda.lote_id == EventoLote.lote_id).join(
        Venda, Venda.venda_id == ItVenda.venda_id
    ).join(Evento, Evento.evento_id == EventoLote.evento_id).filter(
        *filtros_mes,
        EventoLote.organizacao_id == organizacao_id,
        Evento.organizacao_id == organizacao_id,
    )
    if loja_id is not None:
        ingressos_query = ingressos_query.filter(
            EventoLote.loja_id == loja_id,
            Evento.loja_id == loja_id,
        )
    ingressos_rows = ingressos_query.group_by(
        EventoLote.lote_id,
        Evento.nmtituloevento,
        EventoLote.nmlote,
    ).order_by(quantidade_ingresso.desc(), Evento.nmtituloevento, EventoLote.nmlote).all()

    return {
        "periodo": {"inicio": primeiro_dia, "fim": hoje},
        "total_hoje": _dinheiro(total_hoje),
        "total_mes": total_mes,
        "pedidos_mes": int(resumo.pedidos_mes or 0),
        "ingressos_vendidos_mes": int(ingressos_vendidos or 0),
        "participacao_lojas": participacao_lojas,
        "produtos_mais_vendidos": [
            {
                "produto_id": int(row.produto_id),
                "nome": row.nome,
                "quantidade": int(row.quantidade or 0),
                "valor": _dinheiro(row.valor),
            }
            for row in produtos_rows
        ],
        "ingressos_mais_vendidos": [
            {
                "lote_id": int(row.lote_id),
                "nome": f"{row.nmtituloevento} - {row.nmlote}",
                "quantidade": int(row.quantidade or 0),
                "valor": _dinheiro(row.valor),
            }
            for row in ingressos_rows
        ],
    }
