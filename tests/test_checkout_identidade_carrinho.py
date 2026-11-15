import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.services.venda_gateway_service import criar_venda_paga_por_carrinho_gateway


@pytest.mark.parametrize('campo', ['carrinho_id', 'cliente_id', 'loja_id'])
def test_checkout_divergente_nao_gera_venda(campo):
    carrinho = SimpleNamespace(carrinho_id=17, cliente_id=20, loja_id=3, sitcarrinho='ABERTO')
    checkout = SimpleNamespace(carrinho_id=17, cliente_id=20, loja_id=3)
    setattr(checkout, campo, 999)
    db = MagicMock()
    db.query.return_value.filter.return_value.with_for_update.return_value.first.return_value = carrinho

    with pytest.raises(HTTPException) as erro:
        asyncio.run(criar_venda_paga_por_carrinho_gateway(
            db, carrinho_id=17, gateway='MERCADO_PAGO', pagamento={}, checkout_origem=checkout,
        ))

    assert erro.value.status_code == 409
    db.add.assert_not_called()
    db.commit.assert_not_called()
