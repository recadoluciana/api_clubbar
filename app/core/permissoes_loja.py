from fastapi import HTTPException, status


CARGOS_GERENCIAIS = {"SUPERADMIN", "ADMIN", "GERENTE"}


def validar_gerenciamento_organizacao(payload: dict, organizacao_id: int) -> None:
    cargo = str(payload.get("dscargo") or "").strip().upper()
    if payload.get("role") != "usuario" or cargo not in CARGOS_GERENCIAIS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seu cargo permite somente utilizar as funções operacionais.",
        )


def validar_edicao_organizacao(payload: dict, organizacao_id: int) -> None:
    validar_gerenciamento_organizacao(payload, organizacao_id)
    cargo = str(payload.get("dscargo") or "").strip().upper()
    if cargo != "SUPERADMIN" or payload.get("loja_id") is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o SUPERADMIN pode editar os dados da organizacao.",
        )
    if int(payload.get("organizacao_id") or 0) != int(organizacao_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="O cadastro não pertence à sua organização.",
        )


def validar_edicao_organizacao(payload: dict, organizacao_id: int) -> None:
    validar_gerenciamento_organizacao(payload, organizacao_id)
    cargo = str(payload.get("dscargo") or "").strip().upper()
    if cargo != "SUPERADMIN" or payload.get("loja_id") is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o SUPERADMIN pode editar os dados da organizacao.",
        )


def validar_mutacao_loja(payload: dict, organizacao_id: int, loja_id: int) -> None:
    validar_gerenciamento_organizacao(payload, organizacao_id)
    loja_usuario = payload.get("loja_id")
    if loja_usuario is not None and int(loja_usuario) != int(loja_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você não pode alterar itens desta loja. Seu acesso é somente para consulta.",
        )


def validar_edicao_organizacao(payload: dict, organizacao_id: int) -> None:
    validar_gerenciamento_organizacao(payload, organizacao_id)
    cargo = str(payload.get("dscargo") or "").strip().upper()
    if cargo != "SUPERADMIN" or payload.get("loja_id") is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente o SUPERADMIN pode editar os dados da organizacao.",
        )


def validar_escopo_loja_opcional(
    payload: dict,
    organizacao_id: int,
    loja_id: int | None,
) -> None:
    validar_gerenciamento_organizacao(payload, organizacao_id)
    loja_usuario = payload.get("loja_id")
    if loja_usuario is not None and (
        loja_id is None or int(loja_usuario) != int(loja_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Você somente pode administrar usuários vinculados à sua loja.",
        )
