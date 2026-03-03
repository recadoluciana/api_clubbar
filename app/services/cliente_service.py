from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.cliente import Cliente  # ajuste o caminho se necessário


def _digits(x) -> str:
    if x is None:
        return ""
    return "".join(ch for ch in str(x) if ch.isdigit())


def get_cliente(db: Session, cliente_id: int) -> dict:
    cli = db.query(Cliente).filter(Cliente.cliente_id == int(cliente_id)).first()
    if not cli:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    nome = (cli.nmcliente or "").strip() or "Cliente"
    email = (cli.emailcliente or "").strip() or "cliente@exemplo.com"

    cpf = _digits(cli.nrcpfcliente)
    if len(cpf) != 11:
        raise HTTPException(400, detail="CPF do cliente inválido ou não cadastrado.")

    tel = _digits(cli.nrtelcliente)
    # PagBank quer DDD e número separados
    # Ex: 31999998888 => ddd=31, number=999998888
    ddd = ""
    number = ""
    if len(tel) >= 10:
        ddd    = tel[:2]
        number = tel[2:]
    else:
        # fallback (melhor do que quebrar a requisição)
        ddd    = "31"
        number = tel or "999999999"

    return {
        "cliente_id": int(cli.cliente_id),
        "nome": nome,
        "email": email,
        "cpf": cpf,
        "ddd": ddd,
        "telefone": number,
    }