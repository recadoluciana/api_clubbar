from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.routers.eventos import compartilhar_evento


@patch("app.routers.eventos.imagem_evento", return_value="/uploads/eventos/banner.png")
@patch("app.routers.eventos.PUBLIC_API_BASE_URL", "https://api.clubbar.com.br")
def test_pagina_previa_e_redirecionamento(imagem):
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(
        evento_id=7, loja_id=3, nmtituloevento='Niver & "Festa"'
    )
    html = compartilhar_evento(7, db).body.decode()
    assert 'og:image" content="https://api.clubbar.com.br/uploads/eventos/banner.png"' in html
    assert 'Niver &amp; &quot;Festa&quot;' in html
    assert '/?evento_id=7&amp;loja_id=3' in html
    assert "window.location.replace('/?evento_id=7&loja_id=3')" in html
    imagem.assert_called_once()


def test_evento_nao_publicado_ou_inexistente():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        compartilhar_evento(999, db)
    assert exc.value.status_code == 404
