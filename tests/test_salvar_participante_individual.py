from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.models.reserva_ingresso import ReservaIngresso
from app.models.reserva_ingresso_participante import ReservaIngressoParticipante
from app.routers import reservas_ingressos as router
from app.schemas.reserva_ingresso import ParticipanteReservaIn


def preparar(monkeypatch, gratuito=False):
    reserva = SimpleNamespace(reserva_ingresso_id=1, cliente_id=7, qtreservada=1,
        sitreserva='PREENCHENDO', dtexpiracao=datetime.now() + timedelta(minutes=10),
        vrtotal=Decimal('0' if gratuito else '33'), evento_id=4, compra_evento_id=None)
    db = MagicMock()
    consulta_reserva = MagicMock()
    consulta_reserva.filter.return_value.first.return_value = reserva
    consulta_reserva.filter.return_value.with_for_update.return_value.first.return_value = reserva
    consulta_participante = MagicMock()
    consulta_participante.filter.return_value.first.return_value = None
    db.query.side_effect = lambda model: consulta_reserva if model is ReservaIngresso else consulta_participante
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', MagicMock())
    monkeypatch.setattr(router, '_grupo', lambda *args: [reserva])
    monkeypatch.setattr(router, 'beneficios_validos_para_reserva', lambda *args: {})
    monkeypatch.setattr(router, 'bloquear_evento_para_cortesia', MagicMock())
    monkeypatch.setattr(router, 'validar_cortesia_unica_por_cpf', MagicMock())
    monkeypatch.setattr(router, 'finalizar_reserva_gratuita', MagicMock())
    return db, reserva, consulta_participante


@pytest.mark.parametrize('gratuito', [True, False])
def test_salva_sem_finalizar_ou_modificar_status(monkeypatch, gratuito):
    db, reserva, _ = preparar(monkeypatch, gratuito)
    resultado = router.salvar_participante_individual(1, ParticipanteReservaIn(nome='Maria Lima', cpf='12345678909'), db, {})
    participante = db.add.call_args.args[0]
    assert isinstance(participante, ReservaIngressoParticipante)
    assert participante.nmparticipante == 'Maria Lima'
    assert participante.cpfparticipante == '12345678909'
    assert resultado['ok'] is True
    assert reserva.sitreserva == 'PREENCHENDO'
    db.commit.assert_called_once()
    router.finalizar_reserva_gratuita.assert_not_called()


def test_reserva_expirada_nao_salva(monkeypatch):
    db, reserva, _ = preparar(monkeypatch)
    reserva.dtexpiracao = datetime.now() - timedelta(seconds=1)
    with pytest.raises(HTTPException) as erro:
        router.salvar_participante_individual(1, ParticipanteReservaIn(nome='Maria Lima', cpf='12345678909'), db, {})
    assert erro.value.status_code == 409
    db.commit.assert_not_called()


def test_cpf_repetido_na_compra_nao_salva(monkeypatch):
    db, _, consulta = preparar(monkeypatch)
    consulta.filter.return_value.first.return_value = object()
    with pytest.raises(HTTPException) as erro:
        router.salvar_participante_individual(1, ParticipanteReservaIn(nome='Maria Lima', cpf='12345678909'), db, {})
    assert erro.value.status_code == 422
    db.commit.assert_not_called()