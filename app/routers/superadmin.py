from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_operador_logado

from app.models.itvenda import ItVenda
from app.models.leadparceiro import LeadParceiro
from app.models.leadestabelecimento import LeadEstabelecimento
from app.models.loja import Loja
from app.models.organizacao import Organizacao
from app.models.produto import Produto
from app.models.usuario import Usuario
from app.models.venda import Venda


router = APIRouter(
    prefix="/superadmin",
    tags=["Superadmin"],
)

_FUSO_BRASIL = ZoneInfo("America/Sao_Paulo")


def _limites_data_utc(data_local: date) -> tuple[datetime, datetime]:
    inicio_local = datetime.combine(
        data_local,
        datetime.min.time(),
        tzinfo=_FUSO_BRASIL,
    )
    fim_local = inicio_local + timedelta(days=1)
    return (
        inicio_local.astimezone(timezone.utc).replace(tzinfo=None),
        fim_local.astimezone(timezone.utc).replace(tzinfo=None),
    )


def _limites_hoje_utc() -> tuple[datetime, datetime]:
    return _limites_data_utc(datetime.now(_FUSO_BRASIL).date())


@router.get("/dashboard")
def dashboard_superadmin(
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    hoje_inicio, hoje_fim = _limites_hoje_utc()

    # =========================================================
    # LEADS NOVOS
    # =========================================================

    leads_novos = (
        db.query(func.count(func.distinct(LeadEstabelecimento.leadparceiro_id)))
        .filter(
            LeadEstabelecimento.status == "NOVO",
        )
        .scalar()
        or 0
    )

    total_leads = db.query(func.count(LeadParceiro.leadparceiro_id)).scalar() or 0

    total_lead_estabelecimentos = (
        db.query(func.count(LeadEstabelecimento.leadestabelecimento_id)).scalar()
        or 0
    )

    lead_estabelecimentos_novos = (
        db.query(func.count(LeadEstabelecimento.leadestabelecimento_id))
        .filter(LeadEstabelecimento.status == "NOVO")
        .scalar()
        or 0
    )

    # =========================================================
    # PARCEIROS ATIVOS
    # Toda organização ativa é contabilizada como parceiro
    # =========================================================

    parceiros_ativos = (
        db.query(func.count(Organizacao.organizacao_id))
        .filter(
            Organizacao.sitorganizacao == "ATIVA",
        )
        .scalar()
        or 0
    )

    # =========================================================
    # ESTABELECIMENTOS
    # Considera todas as organizações da plataforma
    # =========================================================

    estabelecimentos_ativos = (
        db.query(func.count(Loja.loja_id))
        .filter(
            Loja.sitloja == "ATIVA",
        )
        .scalar()
        or 0
    )

    estabelecimentos_inativos = (
        db.query(func.count(Loja.loja_id))
        .filter(
            Loja.sitloja == "INATIVA",
        )
        .scalar()
        or 0
    )

    total_estabelecimentos = (
        estabelecimentos_ativos
        + estabelecimentos_inativos
    )

    # =========================================================
    # USUÁRIOS
    # Considera todos os usuários cadastrados na plataforma
    # =========================================================

    total_usuarios = (
        db.query(func.count(Usuario.usuario_id))
        .scalar()
        or 0
    )

    # =========================================================
    # VENDAS PAGAS DE HOJE
    # =========================================================

    vendas_hoje = (
        db.query(func.count(Venda.venda_id))
        .filter(
            Venda.sitvenda == "PAGA",
            Venda.dtcriacao >= hoje_inicio,
            Venda.dtcriacao < hoje_fim,
        )
        .scalar()
        or 0
    )

    valor_vendas_hoje = (
        db.query(
            func.coalesce(
                func.sum(Venda.totalvenda),
                0,
            )
        )
        .filter(
            Venda.sitvenda == "PAGA",
            Venda.dtcriacao >= hoje_inicio,
            Venda.dtcriacao < hoje_fim,
        )
        .scalar()
        or 0
    )

    # =========================================================
    # QUANTIDADE TOTAL DE PRODUTOS VENDIDOS
    # Considera somente vendas pagas
    # P = produto
    # =========================================================

    produtos_vendidos = (
        db.query(
            func.coalesce(
                func.sum(ItVenda.qtitvenda),
                0,
            )
        )
        .join(
            Venda,
            Venda.venda_id == ItVenda.venda_id,
        )
        .filter(
            Venda.sitvenda == "PAGA",
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.sititvenda == "ATIVO",
        )
        .scalar()
        or 0
    )

    # =========================================================
    # QUANTIDADE TOTAL DE INGRESSOS VENDIDOS
    # Considera somente vendas pagas
    # I = ingresso
    # =========================================================

    ingressos_vendidos = (
        db.query(
            func.coalesce(
                func.sum(ItVenda.qtitvenda),
                0,
            )
        )
        .join(
            Venda,
            Venda.venda_id == ItVenda.venda_id,
        )
        .filter(
            Venda.sitvenda == "PAGA",
            ItVenda.tipoitem == "INGRESSO",
            ItVenda.sititvenda == "ATIVO",
        )
        .scalar()
        or 0
    )

    # =========================================================
    # FATURAMENTO CLUBBAR COM PRODUTOS HOJE
    # Soma somente as taxas registradas nos itens.
    # =========================================================

    faturamento_produtos = (
        db.query(
            func.coalesce(
                func.sum(ItVenda.vrtaxaitvenda),
                0,
            )
        )
        .join(
            Venda,
            Venda.venda_id == ItVenda.venda_id,
        )
        .filter(
            Venda.sitvenda == "PAGA",
            Venda.dtcriacao >= hoje_inicio,
            Venda.dtcriacao < hoje_fim,
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.sititvenda == "ATIVO",
        )
        .scalar()
        or 0
    )

    # =========================================================
    # FATURAMENTO CLUBBAR COM INGRESSOS HOJE
    # Soma somente as taxas de conveniencia registradas nos itens.
    # =========================================================

    faturamento_ingressos = (
        db.query(
            func.coalesce(
                func.sum(ItVenda.vrtaxaitvenda),
                0,
            )
        )
        .join(
            Venda,
            Venda.venda_id == ItVenda.venda_id,
        )
        .filter(
            Venda.sitvenda == "PAGA",
            Venda.dtcriacao >= hoje_inicio,
            Venda.dtcriacao < hoje_fim,
            ItVenda.tipoitem == "INGRESSO",
            ItVenda.sititvenda == "ATIVO",
        )
        .scalar()
        or 0
    )

    faturamento_total = (
        faturamento_produtos
        + faturamento_ingressos
    )

    return {
        # Leads
        "total_leads": int(total_leads),
        "leads_novos": int(leads_novos),
        "total_lead_estabelecimentos": int(total_lead_estabelecimentos),
        "lead_estabelecimentos_novos": int(lead_estabelecimentos_novos),

        # Parceiros
        "organizacoes": int(parceiros_ativos),
        "parceiros_ativos": int(parceiros_ativos),

        # Estabelecimentos
        "lojas": int(estabelecimentos_ativos),
        "estabelecimentos_ativos": int(
            estabelecimentos_ativos
        ),
        "estabelecimentos_inativos": int(
            estabelecimentos_inativos
        ),
        "total_estabelecimentos": int(
            total_estabelecimentos
        ),

        # Usuários
        "usuarios": int(total_usuarios),

        # Vendas pagas de hoje
        "vendas_hoje": int(vendas_hoje),
        "valor_vendas_hoje": float(
            valor_vendas_hoje
        ),

        # Quantidades vendidas
        "produtos_vendidos": int(
            produtos_vendidos
        ),
        "ingressos_vendidos": int(
            ingressos_vendidos
        ),

        # Faturamento total por tipo
        "faturamento_produtos": float(
            faturamento_produtos
        ),
        "faturamento_ingressos": float(
            faturamento_ingressos
        ),
        "faturamento_total": float(
            faturamento_total
        ),
    }


@router.get("/organizacoes")
def listar_organizacoes_parceiras(
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(
            Organizacao.organizacao_id,
            Organizacao.nmorganizacao,
            Organizacao.nmresponsavelprincipal,
            Organizacao.emailorganizacao,
            Organizacao.telorganizacao,
            Organizacao.sitorganizacao,
            Organizacao.dtcriacao,
            func.count(func.distinct(Loja.loja_id)).label("quantidade_lojas"),
            func.count(func.distinct(Usuario.usuario_id)).label("quantidade_usuarios"),
        )
        .outerjoin(Loja, Loja.organizacao_id == Organizacao.organizacao_id)
        .outerjoin(Usuario, Usuario.organizacao_id == Organizacao.organizacao_id)
        .group_by(
            Organizacao.organizacao_id,
            Organizacao.nmorganizacao,
            Organizacao.nmresponsavelprincipal,
            Organizacao.emailorganizacao,
            Organizacao.telorganizacao,
            Organizacao.sitorganizacao,
            Organizacao.dtcriacao,
        )
        .order_by(Organizacao.nmorganizacao.asc())
        .all()
    )
    return [
        {
            "organizacao_id": int(row.organizacao_id),
            "nmorganizacao": row.nmorganizacao,
            "nmresponsavelprincipal": row.nmresponsavelprincipal,
            "emailorganizacao": row.emailorganizacao,
            "telorganizacao": row.telorganizacao,
            "sitorganizacao": row.sitorganizacao,
            "dtcriacao": row.dtcriacao,
            "quantidade_lojas": int(row.quantidade_lojas or 0),
            "quantidade_usuarios": int(row.quantidade_usuarios or 0),
        }
        for row in rows
    ]


def _organizacao_existe(db: Session, organizacao_id: int) -> None:
    existe = db.query(Organizacao.organizacao_id).filter(
        Organizacao.organizacao_id == organizacao_id
    ).first()
    if not existe:
        raise HTTPException(status_code=404, detail="Organização não encontrada.")


@router.get("/organizacoes/{organizacao_id}/lojas")
def listar_lojas_da_organizacao(
    organizacao_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    _organizacao_existe(db, organizacao_id)
    lojas = (
        db.query(Loja)
        .filter(Loja.organizacao_id == organizacao_id)
        .order_by(Loja.nmloja.asc())
        .all()
    )
    return [
        {
            "loja_id": int(loja.loja_id),
            "organizacao_id": int(loja.organizacao_id),
            "nmloja": loja.nmloja,
            "endloja": loja.endloja,
            "nrendeloja": loja.nrendeloja,
            "dsbairroloja": loja.dsbairroloja,
            "nrtelloja": loja.nrtelloja,
            "sitloja": loja.sitloja,
            "dtcriacao": loja.dtcriacao,
        }
        for loja in lojas
    ]


@router.get("/organizacoes/{organizacao_id}/usuarios")
def listar_usuarios_da_organizacao(
    organizacao_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    _organizacao_existe(db, organizacao_id)
    rows = (
        db.query(Usuario, Loja.nmloja)
        .outerjoin(Loja, Loja.loja_id == Usuario.loja_id)
        .filter(Usuario.organizacao_id == organizacao_id)
        .order_by(Usuario.nmusuario.asc())
        .all()
    )
    return [
        {
            "usuario_id": int(usuario.usuario_id),
            "organizacao_id": int(usuario.organizacao_id),
            "loja_id": int(usuario.loja_id) if usuario.loja_id else None,
            "nmloja": nmloja,
            "nmusuario": usuario.nmusuario,
            "emailuser": usuario.emailuser,
            "dscargo": usuario.dscargo,
            "situsuario": usuario.situsuario,
            "dtcriacao": usuario.dtcriacao,
        }
        for usuario, nmloja in rows
    ]


@router.get("/vendas-hoje")
def detalhar_vendas_hoje(
    data: date | None = Query(default=None),
    organizacao_id: int | None = Query(default=None, ge=1),
    loja_id: int | None = Query(default=None, ge=1),
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    data_consulta = data or datetime.now(_FUSO_BRASIL).date()
    hoje_inicio, hoje_fim = _limites_data_utc(data_consulta)
    filtros = [
        Venda.sitvenda == "PAGA",
        Venda.dtcriacao >= hoje_inicio,
        Venda.dtcriacao < hoje_fim,
    ]
    if organizacao_id is not None:
        filtros.append(Venda.organizacao_id == organizacao_id)
    if loja_id is not None:
        filtros.append(Venda.loja_id == loja_id)

    eh_ingresso = ItVenda.tipoitem == "INGRESSO"
    taxa_produtos = func.coalesce(
        func.sum(case((eh_ingresso, 0), else_=ItVenda.vrtaxaitvenda)), 0
    ).label("taxa_produtos")
    taxa_ingressos = func.coalesce(
        func.sum(case((eh_ingresso, ItVenda.vrtaxaitvenda), else_=0)), 0
    ).label("taxa_ingressos")

    rows = (
        db.query(
            Organizacao.organizacao_id,
            Organizacao.nmorganizacao,
            Loja.loja_id,
            Loja.nmloja,
            func.count(func.distinct(Venda.venda_id)).label("quantidade_vendas"),
            taxa_produtos,
            taxa_ingressos,
        )
        .select_from(ItVenda)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Loja, Loja.loja_id == Venda.loja_id)
        .join(Organizacao, Organizacao.organizacao_id == Venda.organizacao_id)
        .filter(*filtros, ItVenda.sititvenda == "ATIVO")
        .group_by(
            Organizacao.organizacao_id,
            Organizacao.nmorganizacao,
            Loja.loja_id,
            Loja.nmloja,
        )
        .order_by(Organizacao.nmorganizacao.asc(), Loja.nmloja.asc())
        .all()
    )
    detalhes = [
        {
            "organizacao_id": int(row.organizacao_id),
            "nmorganizacao": row.nmorganizacao,
            "loja_id": int(row.loja_id),
            "nmloja": row.nmloja,
            "quantidade_vendas": int(row.quantidade_vendas or 0),
            "taxa_produtos": float(row.taxa_produtos or 0),
            "taxa_ingressos": float(row.taxa_ingressos or 0),
            "faturamento_total": float(
                (row.taxa_produtos or 0) + (row.taxa_ingressos or 0)
            ),
        }
        for row in rows
    ]
    return {
        "data": data_consulta,
        "quantidade_vendas": sum(item["quantidade_vendas"] for item in detalhes),
        "taxa_produtos": sum(item["taxa_produtos"] for item in detalhes),
        "taxa_ingressos": sum(item["taxa_ingressos"] for item in detalhes),
        "faturamento_total": sum(item["faturamento_total"] for item in detalhes),
        "detalhes": detalhes,
    }
