from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.loja import Loja


def resolver_localidade_entrega(
    db: Session,
    *,
    cidade_informada: str,
    uf_informada: str,
    loja: Loja | None = None,
) -> tuple[Cidade, Estado]:
    """Resolve a cidade/UF do endereço para as chaves do cadastro local."""
    uf = (uf_informada or "").strip().upper()
    cidade = (cidade_informada or "").strip()
    if not uf or not cidade:
        raise HTTPException(422, "Informe a cidade e a UF do endereço de entrega.")

    estado = db.query(Estado).filter(func.upper(Estado.sgestado) == uf).first()
    if not estado:
        raise HTTPException(422, "UF do endereço de entrega não encontrada.")

    filtros_cidade = [func.lower(Cidade.nmcidade) == cidade.lower()]
    if cidade.isdigit():
        numero = int(cidade)
        filtros_cidade.extend([
            Cidade.cidade_id == numero,
            Cidade.cdibgecid == numero,
        ])
    cidade_cadastro = db.query(Cidade).filter(
        Cidade.estado_id == estado.estado_id,
        or_(*filtros_cidade),
    ).first()

    # Alguns cadastros antigos guardavam um identificador local incorreto no
    # campo de cidade. Para não criar novos pedidos com esse dado inválido,
    # usa-se a cidade do estabelecimento quando ela pertence à mesma UF.
    if not cidade_cadastro and cidade.isdigit() and loja and loja.cidade_id:
        cidade_cadastro = db.query(Cidade).filter(
            Cidade.cidade_id == loja.cidade_id,
            Cidade.estado_id == estado.estado_id,
        ).first()

    if not cidade_cadastro:
        raise HTTPException(
            422,
            "Cidade do endereço não encontrada para a UF informada.",
        )
    return cidade_cadastro, estado


def nome_localidade_entrega(
    db: Session,
    *,
    cidade_id: int | None,
    estado_id: int | None,
    cidade_legado: str | None = None,
    uf_legado: str | None = None,
) -> tuple[str, str]:
    """Retorna nomes para exibição, com fallback para pedidos anteriores."""
    if cidade_id and estado_id:
        resultado = db.query(Cidade.nmcidade, Estado.sgestado).join(
            Estado, Estado.estado_id == Cidade.estado_id,
        ).filter(
            Cidade.cidade_id == cidade_id,
            Estado.estado_id == estado_id,
        ).first()
        if resultado:
            return resultado.nmcidade or "", resultado.sgestado or ""
    return (cidade_legado or ""), (uf_legado or "")
