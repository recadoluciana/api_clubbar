import unicodedata

import httpx
from fastapi import HTTPException


def _normalizar(valor: str) -> str:
    return "".join(
        caractere for caractere in unicodedata.normalize("NFKD", valor.casefold())
        if not unicodedata.combining(caractere)
    ).strip()


def validar_cep_lead(cep: str, cidade, estado) -> None:
    if len(cep) != 8 or not cep.isdigit():
        raise HTTPException(422, "Informe um CEP válido com 8 dígitos.")
    if cidade is None or estado is None or cidade.estado_id != estado.estado_id:
        raise HTTPException(422, "Selecione a cidade e o estado do endereço.")
    try:
        resposta = httpx.get(f"https://viacep.com.br/ws/{cep}/json/", timeout=5)
        resposta.raise_for_status()
        dados = resposta.json()
    except (httpx.HTTPError, ValueError) as erro:
        raise HTTPException(503, "Não foi possível conferir o CEP agora. Tente novamente.") from erro
    if dados.get("erro") or not dados.get("cep"):
        raise HTTPException(422, "CEP não encontrado. Confira os 8 dígitos informados.")
    if _normalizar(dados.get("uf") or "") != _normalizar(estado.sgestado):
        raise HTTPException(422, "O estado selecionado não corresponde ao CEP.")
    ibge = str(dados.get("ibge") or "")
    if cidade.cdibgecid and ibge:
        cidade_confere = str(cidade.cdibgecid) == ibge
    else:
        cidade_confere = _normalizar(dados.get("localidade") or "") == _normalizar(cidade.nmcidade)
    if not cidade_confere:
        raise HTTPException(422, "A cidade selecionada não corresponde ao CEP.")
