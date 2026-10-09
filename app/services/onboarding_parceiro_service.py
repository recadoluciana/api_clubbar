from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.loja import Loja
from app.models.titularfinanceiro import TitularFinanceiro
from app.models.eventolote import EventoLote
from app.models.eventoloteglobal import EventoLoteGlobal
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor


def validar_publicacao_loja(db: Session, loja_id: int) -> None:
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(status_code=404, detail='Loja nao encontrada')
    titular = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.organizacao_id == loja.organizacao_id,
        TitularFinanceiro.titularfinanceiro_id == loja.titularfinanceiro_id,
    ).first()
    if not titular or titular.status_asaas != 'APROVADO':
        raise HTTPException(
            status_code=409,
            detail=(
                'ASAAS_PENDENTE: este estabelecimento ainda não pode receber compras porque '
                'a conta de recebimentos no Asaas não foi criada ou ainda não está aprovada. '
                'No Clubbar Partner, acesse Titular financeiro para concluir o cadastro.'
            ),
        )


def evento_possui_ingressos_pagos(db: Session, evento_id: int) -> bool:
    """Informa se o evento tem ao menos um ingresso ativo com cobrança.

    Eventos formados somente por cortesias (preço zero) não movimentam
    recebimentos e, por isso, não exigem subconta Asaas aprovada.
    """
    return (
        db.query(EventoLotePreco.lotepreco_id)
        .join(EventoLote, EventoLote.lote_id == EventoLotePreco.lote_id)
        .join(
            EventoLoteGlobal,
            EventoLoteGlobal.loteglobal_id == EventoLote.loteglobal_id,
        )
        .join(
            EventoSetor,
            EventoSetor.eventosetor_id == EventoLote.eventosetor_id,
        )
        .filter(
            EventoLoteGlobal.evento_id == evento_id,
            EventoLoteGlobal.situacao == "ATIVO",
            EventoLote.situacao == "ATIVO",
            EventoSetor.sitsetor == "ATIVO",
            EventoLotePreco.situacao == "ATIVO",
            EventoLotePreco.vrpreco > 0,
        )
        .first()
        is not None
    )
