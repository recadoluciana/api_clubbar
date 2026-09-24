from fastapi import HTTPException


def exigir_cliente_autenticado(usuario: dict, cliente_id: int) -> None:
    """Impede que um cliente consulte ou pague compras de outra conta."""
    try:
        id_token = int(usuario.get("sub"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Cliente inválido") from exc
    if usuario.get("role") != "cliente" or id_token != cliente_id:
        raise HTTPException(status_code=403, detail="Acesso negado para este cliente")
