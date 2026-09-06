from datetime import datetime

from sqlalchemy.orm import Session

from app.models.agendamensal import AgendaMensal


def obter_ou_criar_agenda(
    db: Session,
    organizacao_id: int,
    loja_id: int,
    data_evento: datetime,
) -> AgendaMensal:
    agenda = db.query(AgendaMensal).filter(
        AgendaMensal.loja_id == loja_id,
        AgendaMensal.ano == data_evento.year,
        AgendaMensal.mes == data_evento.month,
    ).first()
    if agenda:
        return agenda
    agenda = AgendaMensal(
        organizacao_id=organizacao_id,
        loja_id=loja_id,
        ano=data_evento.year,
        mes=data_evento.month,
        statusagenda="RASCUNHO",
    )
    db.add(agenda)
    db.flush()
    return agenda
