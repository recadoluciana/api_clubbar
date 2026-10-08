from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from app.models.eventolote import EventoLote
from app.models.eventoloteglobal import EventoLoteGlobal
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.models.modalidadeingresso import ModalidadeIngresso
from app.utils.datetime_utils import FUSO_BRASIL


def _agora_brasilia() -> datetime:
    """Retorna o horário comercial, sem fuso, usado nos eventos do Clubbar."""
    return datetime.now(FUSO_BRASIL).replace(tzinfo=None)

def criar_lote_setor_com_precos(
    db: Session,
    *,
    organizacao_id: int,
    loja_id: int,
    evento_id: int,
    inicio_evento: datetime,
    preco_inteira: Decimal,
    capacidade: int,
    nome_setor: str = "Pista",
    modalidades_ids: list[int] | None = None,
) -> EventoLote:
    """Cria um único estoque e modalidades de preço que compartilham a capacidade."""
    valor = Decimal(str(preco_inteira)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    meia = (valor / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    nome_setor = nome_setor.strip()
    setor = EventoSetor(organizacao_id=organizacao_id, loja_id=loja_id, evento_id=evento_id, nmsetor=nome_setor, dssetor=f"Setor {nome_setor} do evento", qtcapacidade=int(capacidade), nrordem=1, sitsetor="ATIVO")
    db.add(setor); db.flush()
    # O cadastro rápido também segue o modelo normalizado: um lote global e
    # a configuração desse lote para o setor inicial.
    lote_global = EventoLoteGlobal(
        organizacao_id=organizacao_id,
        loja_id=loja_id,
        evento_id=evento_id,
        nrlote=1,
        nmlote="Lote 1",
        # As datas de eventos são cadastradas no horário de Brasília. Usar o
        # relógio UTC do servidor aqui fazia um evento às 01:00 parecer já
        # encerrado logo após a meia-noite no Brasil.
        dtiniciovenda=_agora_brasilia(),
        dtfimvenda=inicio_evento,
        gatilhovirada="DATA",
        situacao="ATIVO",
    )
    db.add(lote_global); db.flush()
    lote = EventoLote(
        loteglobal_id=lote_global.loteglobal_id,
        eventosetor_id=setor.eventosetor_id,
        qtlimite=int(capacidade),
        qtvendidalote=0,
        situacao="ATIVO",
    )
    db.add(lote); db.flush()
    consulta_modalidades = db.query(ModalidadeIngresso).filter(
        ModalidadeIngresso.situacao == "ATIVO",
    )
    if modalidades_ids:
        consulta_modalidades = consulta_modalidades.filter(
            ModalidadeIngresso.modalidade_id.in_(modalidades_ids)
        )
    else:
        consulta_modalidades = consulta_modalidades.filter(
            ModalidadeIngresso.organizacao_id.is_(None),
            ModalidadeIngresso.tipomodalidade.in_(("PADRAO", "LEGAL")),
        )
    modalidades = consulta_modalidades.order_by(
        ModalidadeIngresso.nrordem, ModalidadeIngresso.modalidade_id
    ).all()
    if not modalidades or not any(item.tipomodalidade == "PADRAO" for item in modalidades):
        raise RuntimeError("Catálogo padrão de modalidades de ingresso incompleto")
    db.add_all(
        EventoLotePreco(
            lote_id=lote.lote_id,
            modalidade_id=item.modalidade_id,
            nmpreco=item.nmmodalidade,
            tipopreco=item.cdmodalidade,
            vrpreco=valor if item.tipomodalidade == "PADRAO" else meia,
            aplicacotalegal=item.aplicacotalegal,
            exigecomprovante=item.exigecomprovante,
            nrordem=ordem,
        )
        for ordem, item in enumerate(modalidades, start=1)
    )
    db.flush()
    return lote

# Mantém a compatibilidade com os agendamentos já existentes.
criar_lote_pista_com_precos = criar_lote_setor_com_precos
criar_ingressos_pista_inteira_meia = criar_lote_setor_com_precos
