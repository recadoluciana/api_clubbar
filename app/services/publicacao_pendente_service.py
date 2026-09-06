from datetime import datetime

from sqlalchemy.orm import Session

from app.models.agendamensal import AgendaMensal
from app.models.cardapio import Cardapio, CardapioVersao


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

    versoes = db.query(CardapioVersao).join(
        Cardapio, Cardapio.cardapio_id == CardapioVersao.cardapio_id
    ).filter(
        Cardapio.organizacao_id == organizacao_id,
        CardapioVersao.statusversao == "AGUARDANDO_ASAAS",
        CardapioVersao.publicaraposaprovacao == "S",
    ).all()
    for versao in versoes:
        db.query(CardapioVersao).filter(
            CardapioVersao.cardapio_id == versao.cardapio_id,
            CardapioVersao.cardapioversao_id != versao.cardapioversao_id,
            CardapioVersao.statusversao == "PUBLICADA",
        ).update({"statusversao": "SUBSTITUIDA"}, synchronize_session=False)
        versao.statusversao = (
            "PROGRAMADA" if versao.dtiniciovigencia and versao.dtiniciovigencia > agora else "PUBLICADA"
        )
        versao.publicaraposaprovacao = "N"
        versao.dtpublicacao = agora
    return {"agendas_publicadas": len(agendas), "cardapios_publicados": len(versoes)}
