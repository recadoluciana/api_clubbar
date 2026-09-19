from datetime import datetime, timezone
from typing import Any

from fastapi.responses import JSONResponse

from app.utils.datetime_utils import FUSO_BRASIL


# Datas operacionais são gravadas pelo MySQL/Railway em UTC. Datas de negócio,
# como início de evento e período de vendas, não entram nesta lista porque são
# informadas diretamente no horário local pelo usuário.
_CAMPOS_DATA_OPERACIONAL = {
    "criado_em",
    "atualizado_em",
    "dtaceite",
    "dtalteracao",
    "dtcancelamento",
    "dtconfirmacao",
    "dtconftranspagvenda",
    "dtconversao",
    "dtcriacao",
    "dtdisponibilizacao",
    "dtentregaitvenda",
    "dtexpiracao",
    "dtexpiraitvenda",
    "dtisencao",
    "dtliberacao",
    "dtmovimento",
    "dtpagamento",
    "dtpublicacao",
    "dtultatu",
    "dtultima_mensagem",
    "dtultimaverificacao",
    "dtultimoacesso",
    "dtutilizacao",
    "dtvenda",
}


def _data_local_sem_fuso(valor: Any) -> Any:
    if isinstance(valor, datetime):
        data = valor
    elif isinstance(valor, str):
        try:
            data = datetime.fromisoformat(valor.replace("Z", "+00:00"))
        except ValueError:
            return valor
    else:
        return valor

    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    local = data.astimezone(FUSO_BRASIL).replace(tzinfo=None)
    return local.isoformat(timespec="seconds")


def datas_operacionais_no_fuso_local(conteudo: Any) -> Any:
    if isinstance(conteudo, list):
        return [datas_operacionais_no_fuso_local(item) for item in conteudo]
    if isinstance(conteudo, tuple):
        return [datas_operacionais_no_fuso_local(item) for item in conteudo]
    if not isinstance(conteudo, dict):
        return conteudo

    convertido = {}
    for chave, valor in conteudo.items():
        if str(chave).lower() in _CAMPOS_DATA_OPERACIONAL and valor is not None:
            convertido[chave] = _data_local_sem_fuso(valor)
        else:
            convertido[chave] = datas_operacionais_no_fuso_local(valor)
    return convertido


class ClubbarJSONResponse(JSONResponse):
    """Entrega datas automáticas no horário brasileiro esperado pelos apps."""

    def render(self, content: Any) -> bytes:
        return super().render(datas_operacionais_no_fuso_local(content))
