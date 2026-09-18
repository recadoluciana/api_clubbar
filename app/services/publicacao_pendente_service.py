from datetime import datetime

from sqlalchemy.orm import Session

from app.models.agendamensal import AgendaMensal


def publicar_conteudos_aguardando_asaas(
    db: Session,
    organizacao_id: int,
    *,
    loja_ids: list[int] | None = None,
) -> dict:
    agora = datetime.now()
    consulta = db.query(AgendaMensal).filter(
        AgendaMensal.organizacao_id == organizacao_id,
        AgendaMensal.statusagenda == "AGUARDANDO_ASAAS",
        AgendaMensal.publicaraposaprovacao == "S",
    )
    if loja_ids is not None:
        consulta = consulta.filter(AgendaMensal.loja_id.in_(loja_ids))
    agendas = consulta.all()
    for agenda in agendas:
        agenda.statusagenda = "PUBLICADA"
        agenda.publicaraposaprovacao = "N"
        agenda.dtpublicacao = agora

    return {"agendas_publicadas": len(agendas), "cardapios_publicados": 0}
