from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass

import httpx

from app.core.config import OPENAI_API_KEY, OPENAI_MODEL


logger = logging.getLogger(__name__)
_OPENAI_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class RespostaCoraIA:
    resposta: str
    encaminhar_atendimento: bool


def _texto_da_resposta(dados: dict) -> str:
    for item in dados.get("output") or []:
        if item.get("type") != "message":
            continue
        for conteudo in item.get("content") or []:
            if conteudo.get("type") == "output_text" and conteudo.get("text"):
                return str(conteudo["text"])
    return ""


async def _moderacao_segura(texto: str) -> bool:
    async with httpx.AsyncClient(timeout=20) as client:
        resposta = await client.post(
            f"{_OPENAI_URL}/moderations",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": "omni-moderation-latest", "input": texto},
        )
    resposta.raise_for_status()
    dados = resposta.json()
    resultados = dados.get("results") or []
    return not resultados or not bool(resultados[0].get("flagged"))


async def responder_com_ia(
    *,
    pergunta: str,
    duvidas_frequentes: list[tuple[str, str]],
    historico: list[tuple[str, str]],
    cliente_id: int,
) -> RespostaCoraIA | None:
    """Responde perguntas gerais sem executar operações nem expor dados."""
    if not OPENAI_API_KEY:
        return None

    try:
        if not await _moderacao_segura(pergunta):
            return RespostaCoraIA(
                resposta=(
                    "Não consigo ajudar com esse conteúdo. Se você precisar de "
                    "atendimento, escreva de outra forma e nossa equipe poderá "
                    "acompanhar sua solicitação."
                ),
                encaminhar_atendimento=True,
            )

        base_conhecimento = "\n".join(
            f"- Pergunta: {pergunta_faq}\n  Resposta: {resposta_faq}"
            for pergunta_faq, resposta_faq in duvidas_frequentes
        )
        contexto = "\n".join(
            f"{origem}: {mensagem}" for origem, mensagem in historico[-6:]
        )
        instrucoes = """
Você é a Cora, assistente virtual do Clubbar. Responda em português do Brasil,
com educação, clareza e no máximo 700 caracteres. Use somente as informações
fornecidas nas dúvidas frequentes e no contexto. Nunca invente regras, prazos,
valores, status de pagamento ou dados de uma conta. Não afirme que realizou
ações. Se a pergunta depender da situação específica do cliente, de uma compra,
pagamento, estorno, cadastro, segurança ou de informação ausente, marque
encaminhar_atendimento como true e explique brevemente que a equipe Clubbar
precisa verificar. Caso consiga responder com segurança usando a base,
marque encaminhar_atendimento como false.
""".strip()
        entrada = (
            f"DÚVIDAS FREQUENTES:\n{base_conhecimento}\n\n"
            f"HISTÓRICO RECENTE:\n{contexto or 'Sem histórico anterior.'}\n\n"
            f"PERGUNTA ATUAL:\n{pergunta}"
        )
        identificador = hashlib.sha256(
            f"clubbar-cora:{cliente_id}".encode("utf-8")
        ).hexdigest()
        corpo = {
            "model": OPENAI_MODEL,
            "instructions": instrucoes,
            "input": entrada,
            "store": False,
            "max_output_tokens": 350,
            "safety_identifier": identificador,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "resposta_cora",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "properties": {
                            "resposta": {"type": "string"},
                            "encaminhar_atendimento": {"type": "boolean"},
                        },
                        "required": ["resposta", "encaminhar_atendimento"],
                        "additionalProperties": False,
                    },
                }
            },
        }
        async with httpx.AsyncClient(timeout=35) as client:
            resposta = await client.post(
                f"{_OPENAI_URL}/responses",
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=corpo,
            )
        resposta.raise_for_status()
        conteudo = json.loads(_texto_da_resposta(resposta.json()))
        texto = " ".join(str(conteudo.get("resposta") or "").split())[:700]
        if not texto:
            return None
        return RespostaCoraIA(
            resposta=texto,
            encaminhar_atendimento=bool(
                conteudo.get("encaminhar_atendimento", True)
            ),
        )
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        logger.exception("Falha ao gerar resposta inteligente da Cora")
        return None
