import pytest
from fastapi import HTTPException

from app.routers.entregas import (
    get_qt_itens_naoentregues,
    listar_itens_nao_entregues,
    listar_lojas_com_retirada_pendente,
)


@pytest.mark.parametrize('endpoint,argumentos', [
    (listar_itens_nao_entregues, {'loja_id': 1}),
    (get_qt_itens_naoentregues, {'loja_id': 0}),
    (listar_lojas_com_retirada_pendente, {}),
])
@pytest.mark.parametrize('usuario', [
    {'role': 'cliente', 'sub': '2'},
    {'role': 'usuario', 'sub': '1'},
])
def test_carteira_rejeita_outra_conta_antes_de_consultar_banco(endpoint, argumentos, usuario):
    with pytest.raises(HTTPException) as erro:
        endpoint(cliente_id=1, db=None, usuario=usuario, **argumentos)
    assert erro.value.status_code == 403
