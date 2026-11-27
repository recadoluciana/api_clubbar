from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers import reservas_ingressos as router


def payload(quantidade=1):
    return router.ResgateDiretoIn(cliente_id=7, lote_id=2, lotepreco_id=3,
        quantidade=quantidade, participante={'nome': 'Pessoa Teste', 'cpf': '12345678909'})


def test_resgata_cortesia_individual_sem_sacola(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', MagicMock())
    monkeypatch.setattr(router, '_eh_cortesia', lambda *args: True)
    criar = MagicMock(return_value=SimpleNamespace(reserva_ingresso_id=12, vrtotal=Decimal('0.00')))
    monkeypatch.setattr(router, 'criar_reserva', criar)
    informar = MagicMock(return_value={'gratuito': True, 'venda_id': 30})
    monkeypatch.setattr(router, 'informar_participantes', informar)
    resultado = router.resgatar_cortesia_direta(payload(), db, {})
    assert resultado['gratuito'] is True
    assert criar.call_args.kwargs['quantidade'] == 1
    assert informar.call_args.args[0] == 12
    assert informar.call_args.args[1].participantes[0].cpf == '12345678909'
    db.rollback.assert_not_called()


def test_rejeita_ingresso_pago_e_reverte(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', MagicMock())
    monkeypatch.setattr(router, '_eh_cortesia', lambda *args: False)
    criar = MagicMock()
    monkeypatch.setattr(router, 'criar_reserva', criar)
    with pytest.raises(HTTPException) as erro:
        router.resgatar_cortesia_direta(payload(), db, {})
    assert erro.value.status_code == 422
    criar.assert_not_called()
    db.rollback.assert_called_once()


def test_falha_de_validacao_reverte_reserva(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', MagicMock())
    monkeypatch.setattr(router, '_eh_cortesia', lambda *args: True)
    monkeypatch.setattr(router, 'criar_reserva', MagicMock(return_value=SimpleNamespace(reserva_ingresso_id=12, vrtotal=0)))
    monkeypatch.setattr(router, 'informar_participantes', MagicMock(side_effect=HTTPException(409, 'CPF já utilizado')))
    with pytest.raises(HTTPException):
        router.resgatar_cortesia_direta(payload(), db, {})
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_nao_permite_duas_cortesias_no_mesmo_resgate(monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', MagicMock())
    with pytest.raises(HTTPException) as erro:
        router.resgatar_cortesia_direta(payload(2), db, {})
    assert erro.value.status_code == 422
    db.commit.assert_not_called()