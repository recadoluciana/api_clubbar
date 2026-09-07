from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.eventolote import EventoLote
from app.models.eventosetor import EventoSetor


def criar_ingressos_pista_inteira_meia(
    db: Session,
    *,
    organizacao_id: int,
    loja_id: int,
    evento_id: int,
    inicio_evento: datetime,
    preco_inteira: Decimal,
    capacidade: int,
) -> tuple[EventoLote, EventoLote]:
    """Cria o lote inicial com Pista Inteira e Pista Meia Entrada."""
    capacidade = int(capacidade)
    quantidade_meia = max(1, int(capacidade * 0.40))
    quantidade_inteira = capacidade - quantidade_meia
    valor_inteira = Decimal(str(preco_inteira)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    valor_meia = (valor_inteira / Decimal("2")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    setor = EventoSetor(
        organizacao_id=organizacao_id,
        loja_id=loja_id,
        evento_id=evento_id,
        nmsetor="Pista",
        dssetor="Área geral do evento",
        qtcapacidade=capacidade,
        nrordem=1,
        sitsetor="ATIVO",
    )
    db.add(setor)
    db.flush()

    dados_comuns = {
        "organizacao_id": organizacao_id,
        "loja_id": loja_id,
        "evento_id": evento_id,
        "eventosetor_id": setor.eventosetor_id,
        "nrlote": 1,
        "qtvendidalote": 0,
        "dtiniciovenda": datetime.now(),
        "dtfimvenda": inicio_evento + timedelta(hours=2),
        "statuslote": "ATIVO",
    }
    inteira = EventoLote(
        **dados_comuns,
        tipoingresso="INTEIRA",
        nmlote="Lote 1 - Pista Inteira",
        vrprecolote=valor_inteira,
        qttotallote=quantidade_inteira,
    )
    meia = EventoLote(
        **dados_comuns,
        tipoingresso="MEIA",
        nmlote="Lote 1 - Pista Meia Entrada",
        vrprecolote=valor_meia,
        qttotallote=quantidade_meia,
    )
    db.add_all([inteira, meia])
    db.flush()
    return inteira, meia
