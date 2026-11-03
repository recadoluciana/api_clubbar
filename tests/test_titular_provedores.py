from types import SimpleNamespace
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.asaas_split_service import obter_conta_asaas_da_loja
from app.routers.lojamercadopago import _titular_autorizado, selecionar_provedor_pagamento, consultar_mp_titular, concluir_autorizacao_mercado_pago
from app.schemas.lojamercadopago import ProvedorPagamentoIn
from app.models.loja import Loja
from app.models.titularfinanceiro import TitularFinanceiro
from app.models.titularmercadopago_pendente import TitularMercadoPagoPendente
from app.routers.pagamentos import consultar_provedor_pagamento_loja


def test_nao_abre_asaas_quando_loja_escolheu_mercado_pago():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(provedor_pagamento='MERCADO_PAGO')
    with pytest.raises(HTTPException) as erro:
        obter_conta_asaas_da_loja(db, 1)
    assert erro.value.status_code == 409
    assert db.query.call_count == 1


@pytest.mark.parametrize('usuario', [
    {'role': 'usuario', 'dscargo': 'ADMIN', 'organizacao_id': 2},
    {'role': 'usuario', 'dscargo': 'ADMIN', 'organizacao_id': 1, 'loja_id': 7},
])
def test_acesso_ao_titular_nao_ultrapassa_organizacao_ou_loja(usuario):
    db = MagicMock()
    with pytest.raises(HTTPException) as erro:
        _titular_autorizado(db, 1, 10, usuario)
    assert erro.value.status_code == 403
    db.query.assert_not_called()


def test_selecao_atualiza_juntos_titular_e_provedor():
    loja = SimpleNamespace(loja_id=1, organizacao_id=1, titularfinanceiro_id=10, provedor_pagamento='ASAAS')
    titular = SimpleNamespace(titularfinanceiro_id=11, sittitular='ATIVO')
    conta = SimpleNamespace(statusintegracao='ATIVA', access_token_criptografado='token')
    db = MagicMock()
    def consulta(modelo):
        query = MagicMock()
        if modelo is Loja:
            query.filter.return_value.with_for_update.return_value.first.return_value = loja
        elif modelo is TitularFinanceiro:
            query.filter.return_value.first.return_value = titular
        else:
            query.filter.return_value.first.return_value = None
        return query
    db.query.side_effect = consulta
    with patch('app.routers.lojamercadopago._loja_autorizada', return_value=loja), patch('app.routers.lojamercadopago._conta_titular', return_value=conta), patch('app.routers.lojamercadopago._saida', return_value={'ok': True}):
        resultado = selecionar_provedor_pagamento(1, ProvedorPagamentoIn(titularfinanceiro_id=11, provedor_pagamento='MERCADO_PAGO'), {}, db)
    assert resultado == {'ok': True}
    assert loja.titularfinanceiro_id == 11
    assert loja.provedor_pagamento == 'MERCADO_PAGO'
    db.commit.assert_called_once()


def test_nao_troca_titular_enquanto_existir_pagamento_pendente():
    loja = SimpleNamespace(loja_id=1, organizacao_id=1, titularfinanceiro_id=10, provedor_pagamento='ASAAS')
    titular = SimpleNamespace(titularfinanceiro_id=11, sittitular='ATIVO')
    db = MagicMock()
    def consulta(modelo):
        query = MagicMock()
        if modelo is Loja:
            query.filter.return_value.with_for_update.return_value.first.return_value = loja
        elif modelo is TitularFinanceiro:
            query.filter.return_value.first.return_value = titular
        else:
            query.filter.return_value.first.return_value = SimpleNamespace()
        return query
    db.query.side_effect = consulta
    with patch('app.routers.lojamercadopago._loja_autorizada', return_value=loja), pytest.raises(HTTPException) as erro:
        selecionar_provedor_pagamento(1, ProvedorPagamentoIn(titularfinanceiro_id=11, provedor_pagamento='MERCADO_PAGO'), {}, db)
    assert erro.value.status_code == 409
    assert loja.titularfinanceiro_id == 10
    assert loja.provedor_pagamento == 'ASAAS'
    db.commit.assert_not_called()


def test_consulta_conta_do_titular_sem_revelar_credenciais():
    db = MagicMock()
    db.query.return_value.filter_by.return_value.first.return_value = None
    titular = SimpleNamespace(titularfinanceiro_id=10)
    conta = SimpleNamespace(statusintegracao='ATIVA', access_token_criptografado='segredo', mercadopago_nome='Conta confirmada', mercadopago_user_id='123')
    with patch('app.routers.lojamercadopago._titular_autorizado', return_value=titular), patch('app.routers.lojamercadopago._conta_titular', return_value=conta):
        resultado = consultar_mp_titular(1, 10, {}, db)
    assert resultado['conectada'] is True
    assert resultado['user_id'] == '123'
    assert 'segredo' not in str(resultado)


def test_callback_oauth_pendente_fica_associado_ao_titular():
    db = MagicMock()
    config = SimpleNamespace(titularfinanceiro_id=11, loja_id=None, oauth_state_hash='state', oauth_state_expira_em=datetime.now())
    db.query.return_value.filter.return_value.first.return_value = config
    db.query.return_value.filter_by.return_value.first.return_value = None
    tokens = {'access_token': 'token', 'user_id': '123'}
    with patch('app.routers.lojamercadopago.trocar_codigo_por_tokens', new=AsyncMock(return_value=tokens)), patch('app.routers.lojamercadopago.obter_nome_usuario', new=AsyncMock(return_value='Conta')), patch('app.routers.lojamercadopago.criptografar_credencial', return_value='cifrado'):
        resposta = asyncio.run(concluir_autorizacao_mercado_pago(code='codigo', state='estado', error=None, db=db))
    assert resposta.status_code == 200
    pendente = db.add.call_args.args[0]
    assert isinstance(pendente, TitularMercadoPagoPendente)
    assert pendente.titularfinanceiro_id == 11
    assert pendente.credenciais == 'cifrado'


def test_nao_troca_para_asaas_se_mercado_pago_nao_estiver_conectado():
    db = MagicMock()
    loja = SimpleNamespace(provedor_pagamento='MERCADO_PAGO', titularfinanceiro_id=11)
    db.query.return_value.filter.return_value.first.side_effect = [loja, None]
    with pytest.raises(HTTPException) as erro:
        asyncio.run(consultar_provedor_pagamento_loja(1, {}, db))
    assert erro.value.status_code == 409
