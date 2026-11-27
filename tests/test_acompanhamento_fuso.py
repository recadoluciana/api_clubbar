from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.routers.acompanhamento_vendas import listar_compras_produtos, _estimar_liquido_produto


def test_estimativa_usa_comissao_historica_e_metodo_de_pagamento():
    assert _estimar_liquido_produto(Decimal('3'), Decimal('0'), 'CREDIT_CARD', 'MERCADO_PAGO', 1) == Decimal('2.85')
    assert _estimar_liquido_produto(Decimal('3'), Decimal('0'), 'PIX', 'MERCADO_PAGO', 1) == Decimal('2.97')
    assert _estimar_liquido_produto(Decimal('3'), Decimal('0.30'), 'CREDIT_CARD', 'MERCADO_PAGO', 1) == Decimal('2.55')
    assert _estimar_liquido_produto(Decimal('3'), Decimal('0.30'), 'PIX', 'MERCADO_PAGO', 1) == Decimal('2.67')
    assert _estimar_liquido_produto(Decimal('0'), None, None, None, None) == Decimal('0.00')
    assert _estimar_liquido_produto(Decimal('3'), None, 'PIX', 'MERCADO_PAGO', 1) is None
    assert _estimar_liquido_produto(Decimal('3'), Decimal('0.30'), 'PIX', 'ASAAS', 1) is None
    assert _estimar_liquido_produto(Decimal('3'), Decimal('0.30'), 'OUTRO', 'MERCADO_PAGO', 1) is None
    assert _estimar_liquido_produto(Decimal('3'), Decimal('0.30'), 'PIX', 'MERCADO_PAGO', 2) is None


def test_compras_filtram_dias_e_informam_fuso_de_brasilia():
    banco = MagicMock()
    query = banco.query.return_value
    for metodo in ("join", "outerjoin", "filter", "order_by", "offset", "limit"):
        getattr(query, metodo).return_value = query
    query.all.return_value = [SimpleNamespace(
        itvenda_id=1, venda_id=34, loja_id=1, nmloja="Loja", cliente_id=1,
        nmcliente="Cliente", emailcliente="", produto_id=1, nmproduto="Água",
        urlfotoproduto=None, quantidade=1, qtitvenda=1, vrunititvenda=3, vrtaxaitvenda=Decimal('0.03'),
        dtcompra=datetime(2026, 11, 16, 0, 53, 57), identregaitvenda="NAO",
        dtentregaitvenda=None, nmuserentregaitvenda=None,
    )]
    with patch("app.routers.acompanhamento_vendas._validar_loja"):
        resultado = listar_compras_produtos(
            situacao="TODOS", loja_id=1, inicio=date(2026, 9, 1),
            fim=date(2026, 11, 15), limite=500, offset=0, db=banco,
            usuario={"role": "usuario", "dscargo": "ADMIN", "organizacao_id": 1},
        )
    valores = [
        criterio.right.value
        for chamada in query.filter.call_args_list
        for criterio in chamada.args
        if getattr(getattr(criterio, "left", None), "name", None) == "dtcriacao"
    ]
    assert valores == [datetime(2026, 9, 1, 0), datetime(2026, 11, 16, 0)]
    assert resultado["itens"][0]["dtcompra"] == "2026-11-16T00:53:57-03:00"
    assert resultado["itens"][0]["valor_total"] == 3
    assert resultado["itens"][0]["valor_apos_comissao"] == 2.97
    query.offset.assert_called_once_with(0)


def test_compras_aplicam_offset_da_paginacao():
    banco = MagicMock()
    query = banco.query.return_value
    for metodo in ("join", "outerjoin", "filter", "order_by", "offset", "limit"):
        getattr(query, metodo).return_value = query
    query.all.return_value = []
    with patch("app.routers.acompanhamento_vendas._validar_loja"):
        listar_compras_produtos(
            situacao="TODOS", loja_id=1, inicio=None, fim=None,
            limite=500, offset=500, db=banco,
            usuario={"role": "usuario", "dscargo": "ADMIN", "organizacao_id": 1},
        )
    query.offset.assert_called_once_with(500)
    query.limit.assert_called_once_with(500)
