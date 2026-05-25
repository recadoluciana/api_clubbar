from datetime import date, datetime, time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db

from app.models.lead_parceiro import LeadParceiro
from app.models.organizacao import Organizacao
from app.models.loja import Loja
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

    leads_novos = (
        db.query(LeadParceiro)
        .filter(
            LeadParceiro.status == "NOVO",
        )
        .count()
    )

    total_organizacoes = (
        db.query(Organizacao)
        .filter(
            Organizacao.sitorganizacao == "ATIVA",
        )
        .count()
    )

    total_lojas = (
        db.query(Loja)
        .filter(
            Loja.sitloja == "ATIVA",
        )
        .count()
    )

    vendas_hoje = (
        db.query(Venda)
        .filter(
            Venda.dtcriacao >= hoje_inicio,
        )
        .filter(
            Venda.dtcriacao <= hoje_fim,
        )
        .count()
    )

    valor_vendas_hoje = (
        db.query(
            func.coalesce(
                func.sum(Venda.totalvenda),
                0,
            )
        )
        .filter(
            Venda.dtcriacao >= hoje_inicio,
        )
        .filter(
            Venda.dtcriacao <= hoje_fim,
        )
        .scalar()
    )

    return {
        "leads_novos": leads_novos,
        "organizacoes": total_organizacoes,
        "lojas": total_lojas,
        "vendas_hoje": vendas_hoje,
        "valor_vendas_hoje": float(
            valor_vendas_hoje,
        ),
    }