from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateTable

from app.models.compra_evento import CompraEvento
from app.models.atracao import Atracao  # Registra a relação usada por EventoAtracao.
from app.models.estilomusical import EstiloMusical
from app.models.eventolote import EventoLote
from app.models.reserva_ingresso import ReservaIngresso
from app.models.reserva_ingresso_participante import ReservaIngressoParticipante
from app.services import venda_reserva_ingresso_service as svc


def test_resgate_apos_exclusao_emite_apenas_ingresso_ativo(monkeypatch):
    engine = create_engine('sqlite:///:memory:')
    with engine.begin() as connection:
        connection.execute(CreateTable(ReservaIngresso.__table__, include_foreign_key_constraints=[]))
    with Session(engine, autoflush=False) as session:
        def reserva(identificador, status):
            return dict(reserva_ingresso_id=identificador, compra_evento_id=10,
                        organizacao_id=1, loja_id=1, cliente_id=1, evento_id=1,
                        lote_id=1, lotepreco_id=1, qtreservada=1,
                        vrunitario=0, pctaxa=0, vrtaxa=0, vrtotal=0,
                        sitreserva=status, dtexpiracao=datetime.now() + timedelta(minutes=15))

        session.execute(ReservaIngresso.__table__.insert(), [
            reserva(1, 'AGUARDANDO_PAGAMENTO'), reserva(2, 'CANCELADA'),
            reserva(3, 'EXPIRADA'),
        ])
        ativa, cancelada, expirada = session.query(ReservaIngresso).order_by(
            ReservaIngresso.reserva_ingresso_id
        ).all()

        participante = SimpleNamespace(
            reserva_ingresso_id=1, nmparticipante='Participante',
            cpfparticipante='12345678909', itvenda_id=None,
        )
        lote = SimpleNamespace(qtvendidalote=0)
        compra = SimpleNamespace(venda_id=None, status='ABERTA', valor_total=Decimal('0'))
        consultas = {m: MagicMock() for m in (ReservaIngressoParticipante, EventoLote, CompraEvento)}
        consultas[ReservaIngressoParticipante].filter.return_value.order_by.return_value.all.return_value = [participante]
        consultas[EventoLote].filter.return_value.with_for_update.return_value.first.return_value = lote
        consultas[CompraEvento].filter.return_value.with_for_update.return_value.first.return_value = compra
        db = MagicMock()
        db.query.side_effect = lambda model: session.query(model) if model is ReservaIngresso else consultas[model]
        adicionados = []

        def adicionar(item):
            adicionados.append(item)
            if item._tipo == 'venda': item.venda_id = 10
            if item._tipo == 'item': item.itvenda_id = 20
            if item._tipo == 'pagamento': item.pagvenda_id = 30

        db.add.side_effect = adicionar
        monkeypatch.setattr(svc, 'Venda', lambda **kw: SimpleNamespace(_tipo='venda', **kw))
        monkeypatch.setattr(svc, 'ItVenda', lambda **kw: SimpleNamespace(_tipo='item', **kw))
        monkeypatch.setattr(svc, 'PagVenda', lambda **kw: SimpleNamespace(_tipo='pagamento', **kw))
        monkeypatch.setattr(svc, '_dados_catalogo_item', lambda *args: {})
        monkeypatch.setattr(svc, 'gerar_token_qr', lambda: 'token')
        monkeypatch.setattr(svc, 'bloquear_evento_para_cortesia', MagicMock())
        monkeypatch.setattr(svc, 'validar_cortesia_unica_por_cpf', MagicMock())

        resultado = svc.finalizar_reserva_gratuita(db, reserva_id=1)

        assert resultado['gratuito'] is True
        assert len([item for item in adicionados if item._tipo == 'item']) == 1
        assert participante.itvenda_id == 20
        assert lote.qtvendidalote == 1
        assert ativa.sitreserva == 'CONFIRMADA'
        assert cancelada.sitreserva == 'CANCELADA'
        assert expirada.sitreserva == 'EXPIRADA'
        with pytest.raises(HTTPException) as erro:
            svc.finalizar_reserva_gratuita(db, reserva_id=2)
        assert erro.value.status_code == 409
    engine.dispose()
