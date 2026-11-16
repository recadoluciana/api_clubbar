from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.routers.acompanhamento_vendas import listar_compras_produtos


def test_compras_filtram_dias_de_brasilia_e_informam_fuso_utc():
    banco = MagicMock()
    query = banco.query.return_value
    for metodo in ("join", "outerjoin", "filter", "order_by", "limit"):
        getattr(query, metodo).return_value = query
    query.all.return_value = [SimpleNamespace(
        itvenda_id=1, venda_id=34, loja_id=1, nmloja="Loja", cliente_id=1,
        nmcliente="Cliente", emailcliente="", produto_id=1, nmproduto="Água",
        urlfotoproduto=None, quantidade=1, qtitvenda=1, vrunititvenda=3,
        dtcompra=datetime(2026, 11, 16, 0, 53, 57), identregaitvenda="NAO",
        dtentregaitvenda=None, nmuserentregaitvenda=None,
    )]
    with patch("app.routers.acompanhamento_vendas._validar_loja"):
        resultado = listar_compras_produtos(
            situacao="TODOS", loja_id=1, inicio=date(2026, 9, 1),
            fim=date(2026, 11, 15), limite=500, db=banco,
            usuario={"role": "usuario", "dscargo": "ADMIN", "organizacao_id": 1},
        )
    valores = [
        criterio.right.value
        for chamada in query.filter.call_args_list
        for criterio in chamada.args
        if getattr(getattr(criterio, "left", None), "name", None) == "dtcriacao"
    ]
    assert valores == [datetime(2026, 9, 1, 3), datetime(2026, 11, 16, 3)]
    assert resultado["itens"][0]["dtcompra"] == "2026-11-16T00:53:57Z"
