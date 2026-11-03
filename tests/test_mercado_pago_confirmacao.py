import asyncio
import json
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from fastapi import HTTPException
from app.routers import lojamercadopago as r
from app.schemas.lojamercadopago import MercadoPagoConfirmacaoIn

@pytest.mark.parametrize('confirmar', [True, False])
def test_troca_somente_apos_confirmacao(confirmar):
    db = MagicMock()
    atual = SimpleNamespace(mercadopago_user_id='antiga', mercadopago_nome='Antiga', statusintegracao='ATIVA', access_token_criptografado='anterior')
    loja = SimpleNamespace(loja_id=1, organizacao_id=1, provedor_pagamento='MERCADO_PAGO')
    candidato = SimpleNamespace(confirmacao_id='id', expira_em=datetime.now()+timedelta(minutes=1), credenciais=json.dumps(dict(user_id='nova', nome='Nova', access_token='novo')))
    db.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = candidato
    db.query.return_value.filter_by.return_value.first.return_value = None
    with patch.object(r, '_loja_autorizada', return_value=loja), patch.object(r, '_config', return_value=atual), patch.object(r, 'descriptografar_credencial', side_effect=lambda x:x), patch.object(r, 'criptografar_credencial', side_effect=lambda x:x):
        r.confirmar_conta_mercado_pago(1, MercadoPagoConfirmacaoIn(confirmacao_id='id', confirmar=confirmar), {}, db)
    assert atual.mercadopago_user_id == 'antiga'
    assert atual.access_token_criptografado == 'anterior'
    assert atual.statusintegracao == ('INATIVA' if confirmar else 'ATIVA')
    if confirmar:
        nova = db.add.call_args.args[0]
        assert nova.mercadopago_user_id == 'nova'
        assert nova.statusintegracao == 'ATIVA'
    else:
        db.add.assert_not_called()
    db.delete.assert_called_once_with(candidato)
    db.commit.assert_called_once()

@pytest.mark.parametrize('expirado', [True, False])
def test_recusa_confirmacao_expirada_ou_incorreta(expirado):
    db = MagicMock()
    candidato = SimpleNamespace(confirmacao_id='id', expira_em=datetime.now()+timedelta(minutes=-1 if expirado else 1))
    db.query.return_value.filter_by.return_value.with_for_update.return_value.first.return_value = candidato
    with patch.object(r, '_loja_autorizada', return_value=SimpleNamespace(titularfinanceiro_id=None)), pytest.raises(HTTPException) as erro:
        r.confirmar_conta_mercado_pago(1, MercadoPagoConfirmacaoIn(confirmacao_id='id' if expirado else 'errado', confirmar=True), {}, db)
    assert erro.value.status_code == 409
    db.commit.assert_not_called()

def test_callback_preserva_conta_ativa():
    db = MagicMock()
    atual = SimpleNamespace(loja_id=1, mercadopago_user_id='antiga', access_token_criptografado='anterior', statusintegracao='ATIVA')
    db.query.return_value.filter.return_value.first.return_value = atual
    with patch.object(r, '_pendente', return_value=None), patch.object(r, 'trocar_codigo_por_tokens', new=AsyncMock(return_value=dict(user_id='nova', access_token='novo'))), patch.object(r, 'obter_nome_usuario', new=AsyncMock(return_value='Nova')), patch.object(r, 'expira_em', return_value=None), patch.object(r, 'criptografar_credencial', side_effect=lambda x:x):
        resposta = asyncio.run(r.concluir_autorizacao_mercado_pago('codigo','estado',None,db))
    assert resposta.status_code == 200
    assert atual.mercadopago_user_id == 'antiga'
    assert atual.access_token_criptografado == 'anterior'
    assert atual.statusintegracao == 'ATIVA'
    assert db.add.call_args.args[0].loja_id == 1
