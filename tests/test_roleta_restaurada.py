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


def test_giradas_sao_por_produto_no_carrinho_e_mantem_melhor_preco():
    from app.models.carrinho import Carrinho
    from app.models.itcarrinho import ItCarrinho
    agora = datetime(2026, 11, 27, 12)
    carrinho = SimpleNamespace(carrinho_id=5, cliente_id=4, loja_id=2, organizacao_id=1)
    campanha = SimpleNamespace(beneficioprodutocampanha_id=1, tipo="ROLETA", situacao="ATIVA",
        dthrinicio=agora-timedelta(days=1), dthrfim=None, produto_id=3, qtlimite=None)
    itens = [SimpleNamespace(beneficioprodutoresgate_id=None, vrpreco_original=None, vrunitario=10),
             SimpleNamespace(beneficioprodutoresgate_id=None, vrpreco_original=10, vrunitario=7)]
    premios = []
    real = router.BeneficioProdutoResgate
    fake = MagicMock(side_effect=lambda **dados: SimpleNamespace(**dados))
    for campo in ("carrinho_id", "produto_id", "campanha_id", "origem_giro"):
        setattr(fake, campo, getattr(real, campo))
    db = MagicMock()
    def consulta(model):
        q = MagicMock()
        if model is Carrinho:
            q.filter.return_value.with_for_update.return_value.first.return_value = carrinho
        elif model is BeneficioProdutoCampanha:
            q.filter.return_value.with_for_update.return_value.first.return_value = campanha
        elif model is ItCarrinho:
            q.filter.return_value.with_for_update.return_value.all.return_value = itens
        elif model is fake:
            q.filter.return_value.with_for_update.return_value.first.side_effect = lambda: premios[-1] if premios else None
        return q
    db.query.side_effect = consulta
    def adicionar(premio):
        premio.beneficioprodutoresgate_id = 99
        premios.append(premio)
    db.add.side_effect = adicionar
    with patch.object(router, "exigir_cliente_autenticado"), patch.object(router, "_agora", return_value=agora), \
         patch.object(router, "_total_roletas_utilizadas", return_value=0), \
         patch.object(router.secrets, "choice", return_value=20) as sorteio, \
         patch.object(router, "BeneficioProdutoResgate", fake):
        primeiro = router.girar_roleta(1, router.GiroIn(cliente_id=4, carrinho_id=5), {}, db)
        repetido = router.girar_roleta(1, router.GiroIn(cliente_id=4, carrinho_id=5), {}, db)
    assert sorteio.call_count == 2
    assert primeiro["ja_girou"] is False and repetido["ja_girou"] is False
    assert primeiro["percentual_desconto"] == repetido["percentual_desconto"] == 20
    assert itens[0].vrunitario == 8
    assert itens[1].vrunitario == 7
    assert itens[0].beneficioprodutoresgate_id == 99
    assert itens[1].beneficioprodutoresgate_id is None


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
             {"produto_id": 4, "beneficio_resgate_id": 99}]
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


def test_roleta_permite_giros_sucessivos_com_zero_dez_e_vinte():
    from app.models.carrinho import Carrinho
    from app.models.itcarrinho import ItCarrinho
    agora = datetime(2026, 11, 27, 12)
    carrinho = SimpleNamespace(carrinho_id=5, cliente_id=4, loja_id=2, organizacao_id=1)
    campanha = SimpleNamespace(beneficioprodutocampanha_id=1, tipo="ROLETA", situacao="ATIVA",
        dthrinicio=agora-timedelta(days=1), dthrfim=None, produto_id=3, qtlimite=None)
    item = SimpleNamespace(beneficioprodutoresgate_id=None, beneficioprodutocampanha_id=None, vrpreco_original=None, vrunitario=10)
    premios = []
    real = router.BeneficioProdutoResgate
    fake = MagicMock(side_effect=lambda **dados: SimpleNamespace(**dados))
    for campo in ("carrinho_id", "produto_id", "campanha_id", "origem_giro"):
        setattr(fake, campo, getattr(real, campo))
    db = MagicMock()
    def consulta(model):
        q = MagicMock()
        if model is Carrinho:
            q.filter.return_value.with_for_update.return_value.first.return_value = carrinho
        elif model is BeneficioProdutoCampanha:
            q.filter.return_value.with_for_update.return_value.first.return_value = campanha
        elif model is ItCarrinho:
            q.filter.return_value.with_for_update.return_value.all.return_value = [item]
        elif model is fake:
            q.filter.return_value.with_for_update.return_value.first.side_effect = lambda: premios[-1] if premios else None
        return q
    db.query.side_effect = consulta
    def adicionar(premio):
        premio.beneficioprodutoresgate_id = 99
        premios.append(premio)
    db.add.side_effect = adicionar
    with patch.object(router, "exigir_cliente_autenticado"), patch.object(router, "_agora", return_value=agora), \
         patch.object(router.secrets, "choice", side_effect=[0, 10, 20]) as sorteio, \
         patch.object(router, "BeneficioProdutoResgate", fake):
        valores = []
        for percentual in (0, 10, 20):
            resultado = router.girar_roleta(1, router.GiroIn(cliente_id=4, carrinho_id=5), {}, db)
            valores.append((resultado["percentual_desconto"], float(item.vrunitario)))
    assert sorteio.call_count == 3
    assert valores == [(0, 10), (10, 9), (20, 8)]
