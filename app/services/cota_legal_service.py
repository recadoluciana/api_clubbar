"""Cálculos determinísticos da cota legal de meia-entrada.

A lei fixa a cota no evento. Para que cada setor possa apresentar uma
disponibilidade compreensível, distribuímos a cota global proporcionalmente
entre as capacidades dos setores, usando o maior resto para preservar o total.
"""

from math import ceil

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.eventosetor import EventoSetor


def capacidade_venda_evento(db: Session, evento_id: int) -> int:
    return int(
        db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0))
        .filter(
            EventoSetor.evento_id == evento_id,
            EventoSetor.sitsetor == "ATIVO",
        )
        .scalar()
        or 0
    )


def cota_legal_total(capacidade: int, percentual: float) -> int:
    return int(ceil(max(int(capacidade), 0) * float(percentual) / 100))


def cotas_legais_por_setor(
    db: Session, evento_id: int, percentual: float
) -> dict[int, int]:
    setores = (
        db.query(EventoSetor.eventosetor_id, EventoSetor.qtcapacidade)
        .filter(
            EventoSetor.evento_id == evento_id,
            EventoSetor.sitsetor == "ATIVO",
        )
        .order_by(EventoSetor.eventosetor_id)
        .all()
    )
    capacidade = sum(int(item.qtcapacidade or 0) for item in setores)
    alvo = cota_legal_total(capacidade, percentual)
    distribuicao: dict[int, int] = {}
    restos: list[tuple[float, int]] = []
    for item in setores:
        exato = int(item.qtcapacidade or 0) * float(percentual) / 100
        base = int(exato)
        distribuicao[int(item.eventosetor_id)] = base
        restos.append((exato - base, int(item.eventosetor_id)))
    faltam = alvo - sum(distribuicao.values())
    for _, setor_id in sorted(restos, key=lambda item: (-item[0], item[1]))[:faltam]:
        distribuicao[setor_id] += 1
    return distribuicao
