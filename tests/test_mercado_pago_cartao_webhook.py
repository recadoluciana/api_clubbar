import asyncio
import re
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import httpx

from app.services import mercado_pago_service as service


def test_cartao_envia_webhook_do_ambiente():
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.post.return_value = httpx.Response(201, json={'id': 42})
    with patch.object(service.httpx, 'AsyncClient', return_value=client), patch.object(
        service, 'PUBLIC_API_BASE_URL', 'https://api-dev.exemplo.com'
    ):
        asyncio.run(service.criar_pagamento_cartao(
            access_token='token', external_reference='ref', titulo='PRODUTOS',
            valor=Decimal('10'), valor_taxa_clubbar=Decimal('1'),
            card_token='token-cartao', payment_method_id='visa',
            payer_email='teste@exemplo.com', chave_idempotencia='chave',
            nome_loja='Forró do X',
        ))
    assert re.fullmatch(r'Venda - Forró do X - \d{2}/\d{2}/\d{4} \d{2}:\d{2}', client.post.call_args.kwargs['json']['description'])
    assert client.post.call_args.kwargs['json']['notification_url'] == (
        'https://api-dev.exemplo.com/mercado-pago/webhook'
    )
