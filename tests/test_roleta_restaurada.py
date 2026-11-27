from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.beneficio_produto import BeneficioProdutoCampanha, BeneficioProdutoResgate
from app.models.venda import Venda
from app.routers import beneficios_produtos as router
from app.services.venda_service import adicionar_itens_produto_venda


def test_campanha_roleta_coexiste_com_percentual_sem_prazo_final():
    campanha = router.CampanhaIn(organizacao_id=1, loja_id=2, produto_id=3,
        tipo="ROLETA", nmcampanha="Gire a roleta", dthrinicio=datetime(2026, 1, 1))
    assert campanha.dthrfim is None
    assert campanha.percentual_desconto is None


def test_dois_giros_aguardam_24_horas_do_ultimo():
    agora = datetime(2026, 11, 27, 12)
    giros = [SimpleNamespace(dtresgate=agora - timedelta(hours=1)),
             SimpleNamespace(dtresgate=agora - timedelta(hours=2))]
    assert router._proxima_rodada_roleta(giros, agora) == agora + timedelta(hours=23)


def test_giro_permite_campanha_sem_fim_e_emite_desconto():
    agora = datetime(2026, 11, 27, 12)
    campanha = SimpleNamespace(tipo="ROLETA", situacao="ATIVA", dthrinicio=agora-timedelta(days=1),
        dthrfim=None, produto_id=3, qtlimite=None)
    db = MagicMock()
    consulta = db.query.return_value
    consulta.filter.return_value.with_for_update.return_value.first.return_value = campanha
    consulta.join.return_value.filter.return_value.with_for_update.return_value.all.return_value = []
    consulta.join.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    db.add.side_effect = lambda obj: setattr(obj, "beneficioprodutoresgate_id", 99)
    with patch.object(router, "exigir_cliente_autenticado"), patch.object(router, "_agora", return_value=agora), \
         patch.object(router, "_tem_cortesia_pendente", return_value=False), \
         patch.object(router, "_tem_desconto_recente", return_value=False), \
         patch.object(router, "_total_resgates_validos", return_value=0), \
         patch.object(router.secrets, "choice", return_value=20), \
         patch.object(router, "BeneficioProdutoResgate", MagicMock(side_effect=lambda **dados: SimpleNamespace(**dados))) as resgate_mock:
        for campo in ("campanha_id", "cliente_id", "produto_id", "dtresgate"): 
            setattr(resgate_mock, campo, getattr(BeneficioProdutoResgate, campo))
        resultado = router.girar_roleta(1, router.GiroIn(cliente_id=4), {}, db)
    assert resultado["resgate_id"] == 99
    assert resultado["percentual_desconto"] == 20
    assert resultado["expira_em"] is None


def test_premio_expirado_nao_e_aceito_no_fechamento():
    db = MagicMock()
    venda = SimpleNamespace(cliente_id=4)
    premio = SimpleNamespace(cliente_id=4, produto_id=3, campanha_id=1, situacao="DISPONIVEL",
        dtexpiracao=datetime(2000, 1, 1))
    def query(model):
        consulta = MagicMock()
        if model is Venda:
            consulta.filter.return_value.first.return_value = venda
        if model is BeneficioProdutoResgate:
            consulta.filter.return_value.with_for_update.return_value.first.return_value = premio
        if model is BeneficioProdutoCampanha:
            consulta.filter.return_value.all.return_value = []
            consulta.filter.return_value.first.return_value = SimpleNamespace(tipo="PERCENTUAL")
        return consulta
    db.query.side_effect = query
    with pytest.raises(HTTPException) as erro:
        adicionar_itens_produto_venda(db, venda_id=5, itens=[{"produto_id": 3, "beneficio_resgate_id": 99}])
    assert erro.value.status_code == 409
    db.add.assert_not_called()


def test_nao_pode_duplicar_item_premiado_no_carrinho():
    from app.routers.carrinho import adicionar_um_item_carrinho
    db = MagicMock()
    db.execute.return_value.first.return_value = SimpleNamespace(
        vrunitario=8, beneficioprodutoresgate_id=99)
    with pytest.raises(HTTPException) as erro:
        adicionar_um_item_carrinho(1, db)
    assert erro.value.status_code == 422
    db.commit.assert_not_called()


def test_mesmo_premio_nao_pode_ser_incluido_duas_vezes_na_venda():
    db = MagicMock()
    itens = [{"produto_id": 3, "beneficio_resgate_id": 99},
             {"produto_id": 3, "beneficio_resgate_id": 99}]
    with pytest.raises(HTTPException) as erro:
        adicionar_itens_produto_venda(db, venda_id=5, itens=itens)
    assert erro.value.status_code == 409
    db.add.assert_not_called()


def test_economia_legada_e_exibida_apenas_quando_exata():
    from app.routers.carrinho import _economia_roleta_legada
    assert _economia_roleta_legada(19.80, 10) == 2.20
    assert _economia_roleta_legada(0.05, 10) is None

def test_descartar_premio_cancela_o_resgate():
    db = MagicMock()
    premio = SimpleNamespace(situacao="DISPONIVEL")
    db.query.return_value.join.return_value.filter.return_value.with_for_update.return_value.first.return_value = premio
    db.query.return_value.join.return_value.filter.return_value.first.return_value = None
    with patch.object(router, "exigir_cliente_autenticado"):
        assert router.dispensar_premio_roleta(1, 99, router.GiroIn(cliente_id=4), {}, db) == {"ok": True}
    assert premio.situacao == "CANCELADO"
    db.commit.assert_called_once()
