"""Disponibiliza contratos ausentes em desenvolvimento, preservando os existentes."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from sqlalchemy import text
from app.core.config import APP_ENV
from app.database import SessionLocal
from app.models.titularfinanceiro import TitularFinanceiro
from app.services.contrato_automatico import garantir_contrato, LeadEstabelecimento, LeadEstabelecimentoContrato


def main():
    with SessionLocal() as db:
        if APP_ENV not in {"dev", "development"} or db.execute(text("SELECT DATABASE()")).scalar() != "clubbar_dev":
            raise RuntimeError("Esta atualização é exclusiva de clubbar_dev.")
        faltantes = db.query(LeadEstabelecimento).filter(~db.query(LeadEstabelecimentoContrato).filter(
            LeadEstabelecimentoContrato.leadestabelecimento_id == LeadEstabelecimento.leadestabelecimento_id
        ).exists()).all()
        criados = sum(garantir_contrato(db, item) is not None for item in faltantes)
        db.commit()
        print(f"Contratos disponibilizados: {criados}. Contratos existentes preservados.")


if __name__ == "__main__":
    main()
