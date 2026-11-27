from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.models.compra_evento import CompraEvento, CompraEventoItem
from app.routers import reservas_ingressos as router
from app.schemas.reserva_ingresso import ItemReservaIngressoCreate, ReservaIngressoGrupoCreate


def _preparar(monkeypatch, *, gratuito=False, falhar_na=None):
    db = MagicMock()
    adicionados = []
    reservas = []

    def criar(_db, **dados):
        assert dados['quantidade'] == 1
        if falhar_na == len(reservas) + 1:
            raise HTTPException(409, 'Sem ingressos disponíveis')
        valor = Decimal('0.00') if gratuito else Decimal('30.00')
        taxa = Decimal('0.00') if gratuito else Decimal('3.00')
        reserva = SimpleNamespace(
            reserva_ingresso_id=len(reservas) + 1, organizacao_id=1,
            loja_id=2, cliente_id=dados['cliente_id'], evento_id=3,
            qtreservada=1, vrunitario=valor, vrtaxa=taxa, vrtotal=valor + taxa,
            dtexpiracao=datetime(2026, 11, 27, 12, 0) + timedelta(seconds=len(reservas)),
            compra_evento_id=None,
        )
        reservas.append(reserva)
        return reserva

    def adicionar(item):
        adicionados.append(item)
        if isinstance(item, CompraEvento):
            item.compra_evento_id = 42

    db.add.side_effect = adicionar
    monkeypatch.setattr(router, 'criar_reserva', criar)
    monkeypatch.setattr(router, '_eh_cortesia', lambda *args: gratuito)
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', lambda *args: None)
    monkeypatch.setattr(router, '_saida', lambda db, reserva: {
        'reserva_ingresso_id': reserva.reserva_ingresso_id,
        'quantidade': reserva.qtreservada,
        'valor_total': float(reserva.vrtotal),
    })
    return db, reservas, adicionados


def _item(quantidade):
    return ItemReservaIngressoCreate(lote_id=1, lotepreco_id=2, quantidade=quantidade)


@pytest.mark.parametrize('gratuito', [False, True])
def test_primeira_compra_cria_um_item_por_ingresso(monkeypatch, gratuito):
    db, reservas, adicionados = _preparar(monkeypatch, gratuito=gratuito)
    resposta = router.criar_compra_evento_item(_item(2), 7, db, {})
    itens = [item for item in adicionados if isinstance(item, CompraEventoItem)]
    compra = next(item for item in adicionados if isinstance(item, CompraEvento))
    assert [item.reserva_ingresso_id for item in itens] == [1, 2]
    assert [item.quantidade for item in itens] == [1, 1]
    assert [reserva.compra_evento_id for reserva in reservas] == [42, 42]
    assert [item['quantidade'] for item in resposta['itens']] == [1, 1]
    assert resposta['quantidade'] == 2
    assert resposta['valor_total'] == (0 if gratuito else 66)
    assert compra.valor_total == Decimal('0.00' if gratuito else '66.00')
    db.commit.assert_called_once()


def test_falha_no_segundo_ingresso_reverte_transacao(monkeypatch):
    db, _, _ = _preparar(monkeypatch, falhar_na=2)
    with pytest.raises(HTTPException):
        router.criar_compra_evento_item(_item(2), 7, db, {})
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_grupo_cria_reservas_individuais(monkeypatch):
    db, _, adicionados = _preparar(monkeypatch)
    resposta = router.reservar_grupo(ReservaIngressoGrupoCreate(cliente_id=7, itens=[_item(2)]), db, {})
    itens = [item for item in adicionados if isinstance(item, CompraEventoItem)]
    assert [item.reserva_ingresso_id for item in itens] == [1, 2]
    assert [item.quantidade for item in itens] == [1, 1]
    assert resposta['quantidade'] == 2
    assert resposta['valor_total'] == 66
    db.commit.assert_called_once()


def test_limite_de_cortesias_na_primeira_compra(monkeypatch):
    db, reservas, _ = _preparar(monkeypatch, gratuito=True)
    with pytest.raises(HTTPException) as erro:
        router.criar_compra_evento_item(_item(3), 7, db, {})
    assert erro.value.status_code == 422
    assert not reservas
    db.rollback.assert_called_once()

def test_excluir_um_ingresso_mantem_outro_na_compra(monkeypatch):
    db, reservas, _ = _preparar(monkeypatch)
    router.criar_compra_evento_item(_item(2), 7, db, {})
    db.reset_mock()
    excluida, mantida = reservas
    excluida.sitreserva = mantida.sitreserva = 'PREENCHENDO'
    compra = SimpleNamespace(valor_total=Decimal('66.00'), status='ABERTA')
    busca_compra = MagicMock()
    busca_compra.filter.return_value.with_for_update.return_value.first.return_value = compra
    busca_reserva = MagicMock()
    busca_reserva.filter.return_value.with_for_update.return_value.first.return_value = excluida
    busca_reserva.filter.return_value.all.side_effect = lambda: [
        item for item in reservas if item.sitreserva == 'PREENCHENDO'
    ]
    from app.models.reserva_ingresso import ReservaIngresso
    db.query.side_effect = lambda model: (
        busca_compra if model is CompraEvento else
        busca_reserva if model is ReservaIngresso else MagicMock()
    )
    resposta = router.remover_ingresso_compra_evento(42, 1, 7, db, {})
    assert excluida.sitreserva == 'CANCELADA'
    assert mantida.sitreserva == 'PREENCHENDO'
    assert resposta['quantidade'] == 1
    assert resposta['valor_total'] == 33
    assert [item['reserva_ingresso_id'] for item in resposta['itens']] == [2]
    db.commit.assert_called_once()