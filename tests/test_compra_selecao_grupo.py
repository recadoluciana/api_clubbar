from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import main
import pytest
from fastapi import HTTPException
from app.routers import reservas_ingressos as router
from app.schemas.reserva_ingresso import ReservaIngressoGrupoCreate
from app.services.reserva_ingresso_service import PRAZO_RESERVA_INGRESSO


def test_prazo_da_compra_e_de_dez_minutos():
    assert PRAZO_RESERVA_INGRESSO == timedelta(minutes=10)


def montar(monkeypatch, *, falhar=False):
    db = MagicMock()
    prazo = datetime.now() + timedelta(minutes=7)
    compra = SimpleNamespace(compra_evento_id=42, evento_id=3, loja_id=2,
        dtexpiracao=prazo, valor_total=Decimal('33'))
    existente = SimpleNamespace(reserva_ingresso_id=1, qtreservada=1, vrtotal=Decimal('33'))
    busca_compra = MagicMock()
    busca_compra.filter.return_value.with_for_update.return_value.first.return_value = compra
    busca_reservas = MagicMock()
    busca_reservas.filter.return_value.all.return_value = [existente]
    busca_checkout = MagicMock()
    busca_checkout.filter.return_value.first.return_value = None
    db.query.side_effect = lambda modelo: (busca_compra if modelo is router.CompraEvento else
        busca_reservas if modelo is router.ReservaIngresso else busca_checkout)
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', lambda *args: None)
    monkeypatch.setattr(router, '_eh_cortesia', lambda *args: False)
    criadas = []
    def criar(db, **dados):
        if falhar and criadas:
            raise HTTPException(409, 'Estoque esgotado')
        r = SimpleNamespace(reserva_ingresso_id=len(criadas)+2, qtreservada=1,
            evento_id=3, loja_id=2, vrunitario=Decimal('30'), vrtaxa=Decimal('3'),
            vrtotal=Decimal('33'), dtexpiracao=datetime.now()+timedelta(minutes=10))
        criadas.append(r)
        return r
    monkeypatch.setattr(router, 'criar_reserva', criar)
    monkeypatch.setattr(router, '_saida', lambda db, r: {'reserva_ingresso_id': r.reserva_ingresso_id})
    return db, compra, criadas


def payload(qtd=2):
    return ReservaIngressoGrupoCreate(cliente_id=7, itens=[{'lote_id': 2, 'lotepreco_id': 3, 'quantidade': qtd}])


def test_adiciona_varios_em_transacao_preservando_prazo(monkeypatch):
    db, compra, criadas = montar(monkeypatch)
    resposta = router.adicionar_grupo_compra_evento(42, payload(), db, {})
    assert resposta['quantidade'] == 3
    assert resposta['valor_total'] == 99
    assert all(item.dtexpiracao == compra.dtexpiracao for item in criadas)
    db.commit.assert_called_once()


def test_falha_em_um_ingresso_desfaz_grupo(monkeypatch):
    db, compra, criadas = montar(monkeypatch, falhar=True)
    with pytest.raises(HTTPException):
        router.adicionar_grupo_compra_evento(42, payload(), db, {})
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_asaas_nao_cria_novo_pix_para_ingresso(monkeypatch):
    import asyncio
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', lambda *args: None)
    db = MagicMock()
    with pytest.raises(HTTPException) as erro:
        asyncio.run(router.gerar_pix_reserva(1, router.PagamentoReservaIn(cliente_id=7), db, {}))
    assert erro.value.status_code == 409
    assert 'temporariamente indisponível' in erro.value.detail
    db.query.assert_not_called()


def test_nao_altera_compra_com_pagamento_pendente(monkeypatch):
    db, compra, criadas = montar(monkeypatch)
    busca_checkout = MagicMock()
    busca_checkout.filter.return_value.first.return_value = object()
    anterior = db.query.side_effect
    db.query.side_effect = lambda modelo: busca_checkout if modelo is router.CheckoutMercadoPago else anterior(modelo)
    with pytest.raises(HTTPException) as erro:
        router.adicionar_grupo_compra_evento(42, payload(), db, {})
    assert erro.value.status_code == 409
    assert not criadas
    db.rollback.assert_called_once()
    db.commit.assert_not_called()


def test_pix_pendente_impede_cancelar_reserva_ou_remover_ingresso(monkeypatch):
    db = MagicMock()
    reserva = SimpleNamespace(reserva_ingresso_id=1, sitreserva='PREENCHENDO', compra_evento_id=42)
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', lambda *args: None)
    monkeypatch.setattr(router, '_grupo', lambda db, item: [item])
    compra = SimpleNamespace()
    def query(model):
        q = MagicMock()
        if model is router.ReservaIngresso:
            q.filter.return_value.with_for_update.return_value.first.return_value = reserva
        elif model is router.CompraEvento:
            q.filter.return_value.with_for_update.return_value.first.return_value = compra
        else:
            q.filter.return_value.first.return_value = object() if model is router.CheckoutMercadoPago else None
        return q
    db.query.side_effect = query
    for acao in (lambda: router.cancelar_reserva(1, 7, db, {}),
                 lambda: router.remover_ingresso_compra_evento(42, 1, 7, db, {})):
        with pytest.raises(HTTPException) as erro:
            acao()
        assert erro.value.status_code == 409
        assert reserva.sitreserva == 'PREENCHENDO'
        db.commit.assert_not_called()
