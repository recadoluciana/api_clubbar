from datetime import datetime, timedelta
from decimal import Decimal

import main  # Registra todos os relacionamentos dos modelos da aplicação.
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.compra_evento import CompraEvento, CompraEventoItem
from app.models.reserva_ingresso import ReservaIngresso
from app.models.reserva_ingresso_participante import ReservaIngressoParticipante
from app.routers import reservas_ingressos as router


@pytest.mark.parametrize('quantidade', [1, 2])
def test_exclusao_consulta_restantes_com_autoflush_desativado(monkeypatch, quantidade):
    engine = create_engine('sqlite:///:memory:')
    modelos = (CompraEvento, ReservaIngresso, CompraEventoItem, ReservaIngressoParticipante)
    with engine.begin() as conn:
        for modelo in modelos:
            colunas = ', '.join(
                f'"{col.name}" {col.type.compile(dialect=engine.dialect)}'
                + (' PRIMARY KEY' if col.primary_key else '')
                for col in modelo.__table__.columns
            )
            conn.exec_driver_sql(f'CREATE TABLE "{modelo.__tablename__}" ({colunas})')
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', lambda *args: None)
    monkeypatch.setattr(router, '_saida', lambda db, reserva: {
        'reserva_ingresso_id': reserva.reserva_ingresso_id,
        'quantidade': reserva.qtreservada,
    })
    prazo = datetime.now() + timedelta(minutes=15)
    with Session(engine, autoflush=False, expire_on_commit=False) as db:
        db.add(CompraEvento(compra_evento_id=42, cliente_id=7, organizacao_id=1,
            loja_id=2, evento_id=3, status='ABERTA', valor_total=33 * quantidade, dtexpiracao=prazo))
        for numero in range(1, quantidade + 1):
            db.add(ReservaIngresso(reserva_ingresso_id=numero, compra_evento_id=42,
                cliente_id=7, organizacao_id=1, loja_id=2, evento_id=3, lote_id=1,
                lotepreco_id=1, qtreservada=1, vrunitario=30, vrtaxa=3, pctaxa=0,
                vrtotal=33, sitreserva='PREENCHENDO', dtexpiracao=prazo))
            db.add(CompraEventoItem(compra_evento_item_id=numero, compra_evento_id=42,
                tipoitem='INGRESSO', reserva_ingresso_id=numero, quantidade=1,
                valor_unitario=30, valor_taxa=3, subtotal=33))
        db.commit()
        resposta = router.remover_ingresso_compra_evento(42, 1, 7, db, {})
        assert resposta['quantidade'] == quantidade - 1
        assert [item['reserva_ingresso_id'] for item in resposta['itens']] == list(range(2, quantidade + 1))
        assert resposta['valor_total'] == 33 * (quantidade - 1)
        assert db.get(ReservaIngresso, 1).sitreserva == 'CANCELADA'
        compra = db.get(CompraEvento, 42)
        assert compra.valor_total == Decimal(33 * (quantidade - 1))
        assert compra.status == ('CANCELADA' if quantidade == 1 else 'ABERTA')
