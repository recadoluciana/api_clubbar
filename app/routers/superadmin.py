from datetime import date, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db

from app.models.itvenda import ItVenda
from app.models.leadparceiro import LeadParceiro
from app.models.loja import Loja
from app.models.organizacao import Organizacao
from app.models.produto import Produto
from app.models.usuario import Usuario
from app.models.venda import Venda


router = APIRouter(
    prefix="/superadmin",
    tags=["Superadmin"],
)


@router.get("/dashboard")
def dashboard_superadmin(
    db: Session = Depends(get_db),
):
    hoje_inicio = datetime.combine(
        date.today(),
        time.min,
    )

    hoje_fim = datetime.combine(
        date.today(),
        time.max,
    )

    # =========================================================
    # LEADS NOVOS
    # =========================================================

    leads_novos = (
        db.query(func.count(LeadParceiro.leadparceiro_id))
        .filter(
            LeadParceiro.status == "NOVO",
        )
        .scalar()
        or 0
    )

    # =========================================================
    # PARCEIROS ATIVOS
    # Não contabiliza a organização principal do Clubbar (ID 1)
    # =========================================================

    parceiros_ativos = (
        db.query(func.count(Organizacao.organizacao_id))
        .filter(
            Organizacao.sitorganizacao == "ATIVA",
            Organizacao.organizacao_id != 1,
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
            Venda.dtcriacao <= hoje_fim,
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
            Venda.dtcriacao <= hoje_fim,
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
        .join(
            Produto,
            Produto.produto_id == ItVenda.produto_id,
        )
        .filter(
            Venda.sitvenda == "PAGA",
            Produto.idtipoproduto == "P",
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
        .join(
            Produto,
            Produto.produto_id == ItVenda.produto_id,
        )
        .filter(
            Venda.sitvenda == "PAGA",
            Produto.idtipoproduto == "I",
        )
        .scalar()
        or 0
    )

    # =========================================================
    # FATURAMENTO COM PRODUTOS
    # quantidade × valor unitário
    # Considera somente vendas pagas
    # =========================================================

    faturamento_produtos = (
        db.query(
            func.coalesce(
                func.sum(
                    ItVenda.qtitvenda
                    * ItVenda.vrunititvenda
                ),
                0,
            )
        )
        .join(
            Venda,
            Venda.venda_id == ItVenda.venda_id,
        )
        .join(
            Produto,
            Produto.produto_id == ItVenda.produto_id,
        )
        .filter(
            Venda.sitvenda == "PAGA",
            Produto.idtipoproduto == "P",
        )
        .scalar()
        or 0
    )

    # =========================================================
    # FATURAMENTO COM INGRESSOS
    # quantidade × valor unitário
    # Considera somente vendas pagas
    # Não inclui a taxa de conveniência
    # =========================================================

    faturamento_ingressos = (
        db.query(
            func.coalesce(
                func.sum(
                    ItVenda.qtitvenda
                    * ItVenda.vrunititvenda
                ),
                0,
            )
        )
        .join(
            Venda,
            Venda.venda_id == ItVenda.venda_id,
        )
        .join(
            Produto,
            Produto.produto_id == ItVenda.produto_id,
        )
        .filter(
            Venda.sitvenda == "PAGA",
            Produto.idtipoproduto == "I",
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
        "leads_novos": int(leads_novos),

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