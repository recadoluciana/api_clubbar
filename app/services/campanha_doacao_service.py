from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.campanha_doacao import CampanhaDoacao
from app.models.checkout_asaas_doacao import CheckoutAsaasDoacao
from app.models.reserva_ingresso import ReservaIngresso


def obter_campanha_doacao_vigente(
    db: Session,
    *,
    loja_id: int,
    evento_id: int | None = None,
) -> CampanhaDoacao | None:
    """Retorna a campanha específica do evento ou a padrão da loja."""
    agora = datetime.now()
    base = (
        db.query(CampanhaDoacao)
        .filter(
            CampanhaDoacao.loja_id == loja_id,
            CampanhaDoacao.sitcampanha == "ATIVA",
            or_(CampanhaDoacao.dtinicio.is_(None), CampanhaDoacao.dtinicio <= agora),
            or_(CampanhaDoacao.dtfim.is_(None), CampanhaDoacao.dtfim >= agora),
        )
    )
    if evento_id:
        especifica = (
            base.filter(CampanhaDoacao.evento_id == evento_id)
            .order_by(CampanhaDoacao.dtcriacao.desc())
            .first()
        )
        if especifica:
            return especifica
    return (
        base.filter(CampanhaDoacao.evento_id.is_(None))
        .order_by(CampanhaDoacao.dtcriacao.desc())
        .first()
    )


def obter_campanha_para_reserva(
    db: Session, reserva: ReservaIngresso
) -> CampanhaDoacao | None:
    return obter_campanha_doacao_vigente(
        db, loja_id=int(reserva.loja_id), evento_id=int(reserva.evento_id)
    )


def dados_publicos_campanha(campanha: CampanhaDoacao | None) -> dict | None:
    if not campanha:
        return None
    return {
        "campanha_doacao_id": int(campanha.campanhadoacao_id),
        "nome": campanha.nmcampanha,
        "beneficiario": campanha.nmbeficiario,
        "mensagem": campanha.dsmensagem,
        "percentual_doacao": float(campanha.percentual_doacao),
    }


def validar_campanha_para_split(
    campanha: CampanhaDoacao | None, *, wallet_loja: str
) -> None:
    if not campanha:
        return
    wallet = (campanha.asaas_wallet_id or "").strip()
    if not wallet:
        raise HTTPException(422, "A campanha de doação não possui carteira Asaas.")
    if wallet == wallet_loja:
        raise HTTPException(
            422,
            "A carteira da doação deve ser diferente da carteira do estabelecimento.",
        )
    percentual = Decimal(str(campanha.percentual_doacao or 0))
    if percentual <= 0 or percentual > 100:
        raise HTTPException(422, "O percentual da campanha de doação é inválido.")


def registrar_snapshot_doacao(
    db: Session,
    *,
    checkout_asaas_id: int,
    campanha: CampanhaDoacao | None,
) -> None:
    if not campanha:
        return
    db.add(
        CheckoutAsaasDoacao(
            checkout_asaas_id=checkout_asaas_id,
            campanhadoacao_id=campanha.campanhadoacao_id,
            nmcampanha=campanha.nmcampanha,
            nmbeficiario=campanha.nmbeficiario,
            dsmensagem=campanha.dsmensagem,
            chavepix=campanha.chavepix,
            asaas_wallet_id=campanha.asaas_wallet_id,
            percentual_doacao=campanha.percentual_doacao,
        )
    )
