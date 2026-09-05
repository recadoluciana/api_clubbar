from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.auditoria import Auditoria

router = APIRouter(prefix="/auditoria", tags=["Auditoria"])


def _validar_acesso(payload: dict) -> int:
    cargo = str(payload.get("dscargo") or "").strip().upper()
    if payload.get("role") != "usuario" or cargo not in {"SUPERADMIN", "ADMIN"}:
        raise HTTPException(403, "Somente administradores podem consultar a auditoria.")
    try:
        return int(payload["organizacao_id"])
    except (KeyError, TypeError, ValueError):
        raise HTTPException(403, "Organização não identificada no login.")


@router.get("")
def listar_auditoria(
    busca: str | None = None,
    tabela: str | None = None,
    acao: str | None = None,
    loja_id: int | None = Query(default=None, ge=1),
    dias: int = Query(default=30, ge=1, le=3650),
    limite: int = Query(default=300, ge=1, le=500),
    payload=Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _validar_acesso(payload)
    query = db.query(Auditoria).filter(
        Auditoria.organizacao_id == organizacao_id,
        Auditoria.dtcriacao >= datetime.now() - timedelta(days=dias),
    )
    if tabela and tabela.strip():
        query = query.filter(Auditoria.tabela == tabela.strip())
    if loja_id is not None:
        query = query.filter(Auditoria.loja_id == loja_id)
    if acao and acao.strip():
        query = query.filter(Auditoria.acao == acao.strip().upper())
    if busca and busca.strip():
        termo = f"%{busca.strip()}%"
        query = query.filter(
            or_(
                Auditoria.ator_nome.like(termo),
                Auditoria.ator_email.like(termo),
                Auditoria.tabela.like(termo),
                Auditoria.registro_id.like(termo),
                Auditoria.rota.like(termo),
            )
        )
    itens = query.order_by(Auditoria.dtcriacao.desc()).limit(limite).all()
    return [
        {
            "auditoria_id": item.auditoria_id,
            "organizacao_id": item.organizacao_id,
            "loja_id": item.loja_id,
            "tabela": item.tabela,
            "registro_id": item.registro_id,
            "acao": item.acao,
            "ator_tipo": item.ator_tipo,
            "ator_id": item.ator_id,
            "usuario_id": item.usuario_id,
            "ator_nome": item.ator_nome,
            "ator_email": item.ator_email,
            "dados_anteriores": item.dados_anteriores,
            "dados_novos": item.dados_novos,
            "metodo_http": item.metodo_http,
            "rota": item.rota,
            "dtcriacao": item.dtcriacao,
        }
        for item in itens
    ]
