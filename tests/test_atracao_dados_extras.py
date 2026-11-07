import json
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers.atracoes import _aplicar_dados_extras


def test_dados_extras_preservam_imagens_e_permitem_limpar_contato():
    atracao = SimpleNamespace(instagram="@antigo", urlfoto2atracao="foto.jpg")
    _aplicar_dados_extras(atracao, json.dumps({"instagram": "", "video_youtube": "https://youtu.be/abc"}), None, None)
    assert atracao.instagram is None
    assert atracao.video_youtube == "https://youtu.be/abc"
    assert atracao.urlfoto2atracao == "foto.jpg"
    _aplicar_dados_extras(atracao, '{"remover_foto2": true}', None, None)
    assert atracao.urlfoto2atracao is None


@pytest.mark.parametrize("campo,valor", [
    ("video_youtube", "https://youtube.com.exemplo.com/video"),
    ("video_instagram", "javascript:alert(1)"),
    ("instagram", "https://exemplo.com/perfil"),
])
def test_rejeita_links_de_outros_dominios(campo, valor):
    with pytest.raises(HTTPException) as erro:
        _aplicar_dados_extras(SimpleNamespace(), json.dumps({campo: valor}), None, None)
    assert erro.value.status_code == 422
