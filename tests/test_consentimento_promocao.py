from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.routers.consentimento_promocao import PreferenciasPromocao, _cliente, atualizar, consultar


def test_preferencias_padrao_sao_globais_e_ativadas():
    assert PreferenciasPromocao().model_dump() == {'push': True, 'email': True, 'novidades': True}


def test_parceiro_nao_pode_alterar_preferencias_de_cliente():
    with pytest.raises(HTTPException) as erro:
        _cliente({'role': 'usuario', 'sub': '1'}, MagicMock())
    assert erro.value.status_code == 403


def test_preferencias_sao_lidas_e_salvas_no_cliente():
    cliente = SimpleNamespace(recebe_push_promocoes=True, recebe_email_promocoes=True, recebe_novidades_email=True)
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = cliente
    usuario = {'role': 'cliente', 'sub': '42'}
    assert consultar(usuario, db) == {'push': True, 'email': True, 'novidades': True}
    preferencias = PreferenciasPromocao(push=False, email=False, novidades=True)
    assert atualizar(preferencias, usuario, db) == {'push': False, 'email': False, 'novidades': True}
    assert consultar(usuario, db) == {'push': False, 'email': False, 'novidades': True}
    db.commit.assert_called_once()
