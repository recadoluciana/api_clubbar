from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.routers.acompanhamento_vendas import _resumo_financeiro_ingressos, _valores_lote


def executar(itens, todos, pagamentos, checkouts):
    db = MagicMock()
    db.query.return_value.join.return_value.join.return_value.filter.return_value.all.return_value = itens
    db.query.return_value.filter.return_value.all.side_effect = [todos, pagamentos, checkouts]
    return _resumo_financeiro_ingressos(db, 1)


def test_valores_do_lote_incluem_taxas_e_preservam_dados_ausentes():
    assert _valores_lote(Decimal('5'), Decimal('6.08'), 0) == {'taxas_cobradas': 6.08, 'bruto_itens': 11.08}
    assert _valores_lote(Decimal('5'), Decimal('0'), 1) == {'taxas_cobradas': None, 'bruto_itens': None}


def test_resume_valor_pago_e_previsao_a_partir_do_split():
    item = SimpleNamespace(venda_id=1, itvenda_id=5)
    pag = SimpleNamespace(venda_id=1, vrpagvenda=Decimal('5.54'), dsmetodopag='CREDITO', provedor='MERCADO_PAGO', idtransacaopagvenda='123')
    checkout = SimpleNamespace(venda_id=1, payment_id='123', vrtaxaclubbar=Decimal('2.76'))
    assert executar([item], [item], [pag], [checkout]) == {'bruto_pago': 5.54, 'liquido_previsto': 2.50}


def test_nao_calcula_previsao_sem_checkout_ou_para_venda_mista():
    item = SimpleNamespace(venda_id=1, itvenda_id=5)
    pag = SimpleNamespace(venda_id=1, vrpagvenda=Decimal('5.54'), dsmetodopag='CREDITO', provedor='MERCADO_PAGO', idtransacaopagvenda='123')
    assert executar([item], [item], [pag], []) == {'bruto_pago': 5.54, 'liquido_previsto': None}
    outro = SimpleNamespace(venda_id=1, itvenda_id=6)
    assert executar([item], [item, outro], [pag], []) == {'bruto_pago': None, 'liquido_previsto': None}
