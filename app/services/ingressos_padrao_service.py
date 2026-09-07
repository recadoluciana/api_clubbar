from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from app.models.eventolote import EventoLote
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor

def criar_lote_pista_com_precos(db: Session, *, organizacao_id: int, loja_id: int, evento_id: int, inicio_evento: datetime, preco_inteira: Decimal, capacidade: int) -> EventoLote:
    """Cria um único estoque e modalidades de preço que compartilham a capacidade."""
    valor = Decimal(str(preco_inteira)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    meia = (valor / Decimal("2")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    setor = EventoSetor(organizacao_id=organizacao_id, loja_id=loja_id, evento_id=evento_id, nmsetor="Pista", dssetor="Área geral do evento", qtcapacidade=int(capacidade), nrordem=1, sitsetor="ATIVO")
    db.add(setor); db.flush()
    lote = EventoLote(organizacao_id=organizacao_id, loja_id=loja_id, evento_id=evento_id, eventosetor_id=setor.eventosetor_id, nrlote=1, nmlote="Lote 1 - Pista", qttotallote=int(capacidade), qtvendidalote=0, dtiniciovenda=datetime.now(), dtfimvenda=inicio_evento + timedelta(hours=2), statuslote="ATIVO")
    db.add(lote); db.flush()
    db.add_all([
        EventoLotePreco(lote_id=lote.lote_id, nmpreco="Inteira", tipopreco="INTEIRA", vrpreco=valor, aplicacotalegal=False, exigecomprovante=False, nrordem=1),
        EventoLotePreco(lote_id=lote.lote_id, nmpreco="Meia-entrada", tipopreco="MEIA_LEGAL", vrpreco=meia, aplicacotalegal=True, exigecomprovante=True, nrordem=2),
        EventoLotePreco(lote_id=lote.lote_id, nmpreco="Pessoa idosa", tipopreco="MEIA_IDOSO", vrpreco=meia, aplicacotalegal=False, exigecomprovante=True, nrordem=3),
    ]); db.flush()
    return lote

criar_ingressos_pista_inteira_meia = criar_lote_pista_com_precos
