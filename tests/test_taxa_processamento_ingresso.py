from decimal import Decimal
import pytest
from fastapi import HTTPException
from app.services.taxa_processamento_ingresso import cotar_ingressos_mercado_pago, distribuir_processamento


@pytest.mark.parametrize('metodo,unitario,taxa,qtd,total,mp,comissao', [
    ('PIX', '100.00', '10.00', 1, '112.00', '1.11', '10.89'),
    ('CREDIT_CARD', '100.00', '10.00', 1, '112.00', '5.59', '6.41'),
    ('PIX', '2.50', '0.25', 1, '2.80', '0.03', '0.27'),
    ('CREDIT_CARD', '2.50', '0.25', 1, '2.80', '0.14', '0.16'),
    ('PIX', '2.50', '0.25', 3, '8.40', '0.09', '0.81'),
])
def test_cotacao_repasse_e_taxas(metodo, unitario, taxa, qtd, total, mp, comissao):
    cotacao = cotar_ingressos_mercado_pago(Decimal(unitario), Decimal(taxa), qtd, metodo)
    assert cotacao['total'] == Decimal(total)
    assert cotacao['tarifa_mp_estimada'] == Decimal(mp)
    assert cotacao['comissao_clubbar'] == Decimal(comissao)
    assert cotacao['total'] - cotacao['tarifa_mp_estimada'] - cotacao['comissao_clubbar'] == Decimal(unitario) * qtd


def test_distribui_centavos_para_reembolso_integral():
    valores = distribuir_processamento(Decimal('0.05'), 3)
    assert valores == [Decimal('0.02'), Decimal('0.02'), Decimal('0.01')]
    assert sum(valores) == Decimal('0.05')


def test_cortesia_nao_recebe_taxa():
    with pytest.raises(HTTPException):
        cotar_ingressos_mercado_pago(Decimal('0'), Decimal('0'), 1, 'PIX')


def test_nao_bloqueia_quando_estimativa_excede_as_taxas():
    cotacao = cotar_ingressos_mercado_pago(Decimal('0.01'), Decimal('0.00'), 1, 'CREDIT_CARD')
    assert cotacao['total'] == Decimal('0.01')
    assert cotacao['comissao_clubbar'] == Decimal('0.00')


def test_cotacao_rejeita_reserva_com_subtotal_inconsistente():
    from types import SimpleNamespace
    from app.routers.reservas_ingressos import _cotacao_reserva
    reserva = SimpleNamespace(vrunitario=Decimal('100'), vrtaxa=Decimal('10'), qtreservada=1, vrtotal=Decimal('109'))
    with pytest.raises(HTTPException):
        _cotacao_reserva(reserva, 'PIX')
