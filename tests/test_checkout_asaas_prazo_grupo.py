import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import main
from app.routers import reservas_ingressos as router


def test_checkout_asaas_mantem_todo_grupo_reservado(monkeypatch):
    prazo_original = datetime.now() + timedelta(minutes=3)
    reserva = SimpleNamespace(cliente_id=7, loja_id=2, dtexpiracao=prazo_original)
    outra = SimpleNamespace(dtexpiracao=prazo_original)
    cliente = SimpleNamespace(nmcliente='Teste', emailcliente='teste@example.com',
        nrcpfcliente='12345678909', nrtelcliente='', endcliente='', nrendcliente='',
        complcliente='', bairrocliente='', cepcliente='')
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = cliente
    monkeypatch.setattr(router, 'exigir_cliente_autenticado', MagicMock())
    monkeypatch.setattr(router, '_reserva_para_pagamento', lambda *args: reserva)
    monkeypatch.setattr(router, '_grupo', lambda *args: [reserva, outra])
    monkeypatch.setattr(router, '_valor_grupo', lambda *args: Decimal('20'))
    monkeypatch.setattr(router, '_taxa_grupo', lambda *args: Decimal('2'))
    monkeypatch.setattr(router, 'validar_endereco_cobranca_para_cartao', MagicMock())
    monkeypatch.setattr(router, 'obter_conta_asaas_da_loja', lambda *args: ('key', 'wallet'))
    monkeypatch.setattr(router, 'obter_campanha_para_reserva', lambda *args: None)
    monkeypatch.setattr(router, 'validar_campanha_para_split', lambda *args, **kwargs: None)
    monkeypatch.setattr(router, 'garantir_webhook_pagamentos_asaas', AsyncMock())
    monkeypatch.setattr(router, 'montar_splits_pagamento', lambda *args, **kwargs: [])
    chamada = AsyncMock(return_value={'id': 'checkout-teste', 'link': 'https://example.com'})
    monkeypatch.setattr(router, 'criar_checkout_asaas', chamada)
    monkeypatch.setattr(router, 'registrar_snapshot_doacao', MagicMock())
    inicio = datetime.now()
    resultado = asyncio.run(router.gerar_checkout_reserva(1, router.PagamentoReservaIn(cliente_id=7), db, {}))
    assert chamada.await_args.kwargs['minutes_to_expire'] == 10
    assert reserva.dtexpiracao == outra.dtexpiracao
    assert reserva.dtexpiracao >= inicio + timedelta(minutes=10)
    assert resultado['data_expiracao'] == router.iso_utc(reserva.dtexpiracao)
    db.commit.assert_called_once()
