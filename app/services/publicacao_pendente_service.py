from datetime import datetime

from sqlalchemy.orm import Session

from app.models.agendamensal import AgendaMensal


def publicar_conteudos_aguardando_asaas(db: Session, organizacao_id: int) -> dict:
    agora = datetime.now()
    agendas = db.query(AgendaMensal).filter(
        AgendaMensal.organizacao_id == organizacao_id,
        AgendaMensal.statusagenda == "AGUARDANDO_ASAAS",
        AgendaMensal.publicaraposaprovacao == "S",
    ).all()
    for agenda in agendas:
        agenda.statusagenda = "PUBLICADA"
        agenda.publicaraposaprovacao = "N"
        agenda.dtpublicacao = agora

    return {"agendas_publicadas": len(agendas), "cardapios_publicados": 0}
