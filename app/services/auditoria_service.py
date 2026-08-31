from __future__ import annotations

import enum
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models.auditoria import Auditoria


@dataclass(frozen=True)
class AtorAuditoria:
    tipo: str = "SISTEMA"
    ator_id: str | None = None
    nome: str = "Sistema"
    email: str | None = None
    usuario_id: int | None = None
    operador_id: int | None = None
    metodo_http: str | None = None
    rota: str | None = None


_ator_atual: ContextVar[AtorAuditoria] = ContextVar(
    "ator_auditoria",
    default=AtorAuditoria(),
)
_eventos_registrados = False
_termos_sensiveis = (
    "senha",
    "token",
    "secret",
    "credencial",
    "authorization",
    "qrcode",
    "payloadpix",
)


def definir_ator(ator: AtorAuditoria) -> Token:
    return _ator_atual.set(ator)


def restaurar_ator(token: Token) -> None:
    _ator_atual.reset(token)


def _json_seguro(valor: Any) -> Any:
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, enum.Enum):
        return valor.value
    if isinstance(valor, bytes):
        return f"<bytes:{len(valor)}>"
    if isinstance(valor, (list, tuple, set)):
        return [_json_seguro(item) for item in valor]
    if isinstance(valor, dict):
        return {str(chave): _json_seguro(item) for chave, item in valor.items()}
    return str(valor)


def _valor_coluna(nome: str, valor: Any) -> Any:
    if any(termo in nome.lower() for termo in _termos_sensiveis):
        return "<protegido>" if valor is not None else None
    return _json_seguro(valor)


def _identificador(objeto: Any) -> str:
    estado = inspect(objeto)
    valores = [getattr(objeto, coluna.key, None) for coluna in estado.mapper.primary_key]
    if not valores or any(valor is None for valor in valores):
        return "PENDENTE"
    return ":".join(str(valor) for valor in valores)


def _estado_completo(objeto: Any) -> dict[str, Any]:
    estado = inspect(objeto)
    return {
        atributo.key: _valor_coluna(
            atributo.key,
            getattr(objeto, atributo.key, None),
        )
        for atributo in estado.mapper.column_attrs
    }


def _alteracoes(objeto: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    estado = inspect(objeto)
    anteriores: dict[str, Any] = {}
    novos: dict[str, Any] = {}
    for atributo in estado.mapper.column_attrs:
        historico = estado.attrs[atributo.key].history
        if not historico.has_changes():
            continue
        valor_atual = getattr(objeto, atributo.key, None)
        anteriores[atributo.key] = _valor_coluna(
            atributo.key,
            historico.deleted[0] if historico.deleted else valor_atual
        )
        novos[atributo.key] = _valor_coluna(atributo.key, valor_atual)
    return anteriores, novos


def _criar_evento(objeto: Any, acao: str, anteriores=None, novos=None) -> Auditoria:
    ator = _ator_atual.get()
    return Auditoria(
        tabela=inspect(objeto).mapper.local_table.name,
        registro_id=_identificador(objeto),
        acao=acao,
        ator_tipo=ator.tipo,
        ator_id=ator.ator_id,
        usuario_id=ator.usuario_id,
        operador_id=ator.operador_id,
        ator_nome=ator.nome,
        ator_email=ator.email,
        dados_anteriores=anteriores,
        dados_novos=novos,
        metodo_http=ator.metodo_http,
        rota=ator.rota,
    )


def registrar_eventos_auditoria() -> None:
    global _eventos_registrados
    if _eventos_registrados:
        return
    _eventos_registrados = True

    @event.listens_for(Session, "before_flush")
    def capturar_alteracoes(session: Session, _flush_context, _instances) -> None:
        pendentes = session.info.setdefault("auditoria_pendentes", [])

        for objeto in session.new:
            if not isinstance(objeto, Auditoria):
                pendentes.append(("INCLUSAO", objeto, None, None))

        for objeto in session.dirty:
            if isinstance(objeto, Auditoria) or not session.is_modified(
                objeto, include_collections=False
            ):
                continue
            anteriores, novos = _alteracoes(objeto)
            if novos:
                pendentes.append(("ALTERACAO", objeto, anteriores, novos))

        for objeto in session.deleted:
            if not isinstance(objeto, Auditoria):
                pendentes.append(("EXCLUSAO", objeto, _estado_completo(objeto), None))

    @event.listens_for(Session, "after_flush_postexec")
    def persistir_auditoria(session: Session, _flush_context) -> None:
        pendentes = session.info.pop("auditoria_pendentes", [])
        for acao, objeto, anteriores, novos in pendentes:
            if acao == "INCLUSAO":
                novos = _estado_completo(objeto)
            session.add(_criar_evento(objeto, acao, anteriores, novos))

    @event.listens_for(Session, "after_rollback")
    def descartar_auditoria_de_transacao_cancelada(session: Session) -> None:
        session.info.pop("auditoria_pendentes", None)
