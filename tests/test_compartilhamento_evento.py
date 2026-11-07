import io
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from PIL import Image

from app.routers.eventos import compartilhar_evento, imagem_compartilhamento_evento
from app.models.evento import Evento


@patch("app.routers.eventos.imagem_evento", return_value="/uploads/eventos/banner.png")
@patch("app.routers.eventos.PUBLIC_API_BASE_URL", "https://api.clubbar.com.br")
def test_pagina_previa_e_redirecionamento(imagem):
    db = MagicMock()
    evento = SimpleNamespace(evento_id=7, loja_id=3, nmtituloevento='Niver & "Festa"', nmlocalevento='Salão', dsendlocevento='Rua A, 123')
    db.query.side_effect = lambda model: MagicMock(**{'filter.return_value.first.return_value': evento if model == Evento else None})
    html = compartilhar_evento(7, db).body.decode()
    assert 'og:image" content="https://api.clubbar.com.br/eventos/compartilhar/7/imagem.jpg?v=' in html
    assert 'Local: Salão — Rua A, 123' in html
    assert 'Niver &amp; &quot;Festa&quot;' in html
    assert '/?evento_id=7&amp;loja_id=3' in html
    assert "window.location.replace('/?evento_id=7&loja_id=3')" in html
    imagem.assert_called_once()


@patch("app.routers.eventos.imagem_evento", return_value="/uploads/eventos/banner.png")
@patch("app.routers.eventos.obter_arquivo")
def test_imagem_otimizada(arquivo, imagem):
    original = io.BytesIO()
    Image.new('RGB', (1672, 941), 'red').save(original, format='PNG')
    arquivo.return_value = (original.getvalue(), 'image/png')
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(evento_id=7)
    resposta = imagem_compartilhamento_evento(7, db)
    assert resposta.media_type == 'image/jpeg'
    with Image.open(io.BytesIO(resposta.body)) as resultado:
        assert resultado.width == 1200
    assert len(resposta.body) < 300_000


def test_evento_nao_publicado_ou_inexistente():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    with pytest.raises(HTTPException) as exc:
        compartilhar_evento(999, db)
    assert exc.value.status_code == 404
