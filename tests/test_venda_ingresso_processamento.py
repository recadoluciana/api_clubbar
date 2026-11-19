from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
import pytest
from fastapi import HTTPException
from app.services import venda_reserva_ingresso_service as svc
from app.models.reserva_ingresso import ReservaIngresso
from app.models.reserva_ingresso_participante import ReservaIngressoParticipante
from app.models.eventolote import EventoLote
from app.models.checkout_mercadopago import CheckoutMercadoPago


def _ambiente(monkeypatch, recebido):
    reserva = SimpleNamespace(reserva_ingresso_id=1, organizacao_id=1, loja_id=1, cliente_id=1, venda_id=None, sitreserva='AGUARDANDO_PAGAMENTO', lote_id=1, lotepreco_id=2, qtreservada=3, vrunitario=Decimal('10.00'), pctaxa=Decimal('10'), vrtaxa=Decimal('1.00'), vrtotal=Decimal('33.00'))
    checkout = SimpleNamespace(reserva_ingresso_id=1, valor=Decimal('33.35'), preference_id='ref', external_reference='ref', lojamercadopago_id=1)
    participantes = [SimpleNamespace(nmparticipante='Teste', cpfparticipante='123') for _ in range(3)]
    lote = SimpleNamespace(qtvendidalote=0)
    consultas = {m: MagicMock() for m in (ReservaIngresso, ReservaIngressoParticipante, EventoLote, CheckoutMercadoPago)}
    consultas[ReservaIngresso].filter.return_value.with_for_update.return_value.first.return_value = reserva
    consultas[CheckoutMercadoPago].filter.return_value.with_for_update.return_value.first.return_value = checkout
    consultas[EventoLote].filter.return_value.with_for_update.return_value.first.return_value = lote
    consultas[ReservaIngressoParticipante].filter.return_value.order_by.return_value.all.return_value = participantes
    db=MagicMock(); db.query.side_effect=lambda model: consultas[model]
    adicionados=[]
    def adicionar(item):
        adicionados.append(item)
        if getattr(item, '_tipo', '') == 'venda': item.venda_id=10
        if getattr(item, '_tipo', '') == 'item': item.itvenda_id=len(adicionados)
        if getattr(item, '_tipo', '') == 'pagamento': item.pagvenda_id=30
    db.add.side_effect=adicionar
    monkeypatch.setattr(svc, 'Venda', lambda **kwargs: SimpleNamespace(_tipo='venda', **kwargs))
    monkeypatch.setattr(svc, 'ItVenda', lambda **kwargs: SimpleNamespace(_tipo='item', **kwargs))
    monkeypatch.setattr(svc, 'PagVenda', lambda **kwargs: SimpleNamespace(_tipo='pagamento', **kwargs))
    monkeypatch.setattr(svc, 'gerar_token_qr', lambda: 'token')
    monkeypatch.setattr(svc, '_dados_catalogo_item', lambda *args: {})
    monkeypatch.setattr(svc, 'set_venda_como_paga', MagicMock())
    pagamento={'id':'123', 'status':'approved', 'transaction_amount':recebido, 'payment_method_id':'pix'}
    return db, reserva, checkout, pagamento, adicionados


def test_confirmacao_registra_total_e_taxa_por_ingresso(monkeypatch):
    db, reserva, checkout, pagamento, adicionados=_ambiente(monkeypatch, 33.35)
    resultado=svc.finalizar_reserva_paga(db, reserva_id=1, checkout_id=1, pagamento=pagamento, gateway='MERCADO_PAGO', modelo_checkout=CheckoutMercadoPago)
    itens=[x for x in adicionados if x._tipo=='item']
    assert resultado['venda_id']==10
    assert sum(x.vrunititvenda + x.vrtaxaitvenda for x in itens)==Decimal('33.35')
    assert [x.vrtaxaitvenda for x in itens]==[Decimal('1.12'), Decimal('1.12'), Decimal('1.11')]
    assert next(x for x in adicionados if x._tipo=='pagamento').vrpagvenda==Decimal('33.35')
    assert reserva.vrtotal == Decimal('33.35')
    assert checkout.status=='PAID' and reserva.sitreserva=='CONFIRMADA'


def test_valor_divergente_nao_emite_ingresso(monkeypatch):
    db, _, _, pagamento, adicionados=_ambiente(monkeypatch, 33.00)
    with pytest.raises(HTTPException):
        svc.finalizar_reserva_paga(db, reserva_id=1, checkout_id=1, pagamento=pagamento, gateway='MERCADO_PAGO', modelo_checkout=CheckoutMercadoPago)
    assert adicionados == []
