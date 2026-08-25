from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.loja import Loja
from app.models.titularfinanceiro import TitularFinanceiro


def validar_publicacao_loja(db: Session, loja_id: int) -> None:
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail='Loja nao encontrada')
    titular = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.organizacao_id == loja.organizacao_id
    ).first()
    if not titular or titular.status_asaas != 'APROVADO':
        raise HTTPException(status_code=409, detail='Recebimentos ainda nao aprovados pelo Asaas. Salve como rascunho.')
