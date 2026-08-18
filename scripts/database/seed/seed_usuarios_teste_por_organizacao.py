"""Cria usuarios globais por organizacao e operacionais para cada loja.

Este script e intencionalmente isolado: nao faz parte das migrations nem do
create_schema.sql. Execute a partir da raiz da API:

    python scripts/database/seed/seed_usuarios_teste_por_organizacao.py --senha "SuaSenha123"

Os e-mails sao deterministicos, portanto novas execucoes atualizam os mesmos
usuarios de teste em vez de criar duplicatas.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv


RAIZ_PROJETO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ_PROJETO))
load_dotenv(RAIZ_PROJETO / ".env", override=False)

from app.core.security import hash_senha  # noqa: E402
from app.database import SessionLocal  # noqa: E402
from app.models.loja import Loja  # noqa: E402
from app.models.organizacao import Organizacao  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402


CARGOS_SEM_LOJA = ("SUPERADMIN", "ADMIN")
CARGOS_COM_LOJA = ("GERENTE", "CAIXA", "TOTEM", "BARMAN", "GARCOM", "PORTEIRO")
DOMINIO_TESTE = "clubbar.local"


def _argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--senha",
        required=True,
        help="Senha comum dos usuarios de teste (minimo de 6 caracteres).",
    )
    return parser.parse_args()


def _email(organizacao_id: int, cargo: str, loja_id: int | None = None) -> str:
    loja = f".loja{loja_id}" if loja_id is not None else ""
    return f"teste.{cargo.lower()}.org{organizacao_id}{loja}@{DOMINIO_TESTE}"


def main() -> int:
    args = _argumentos()
    senha = args.senha.strip()
    if len(senha) < 6:
        raise SystemExit("A senha deve ter pelo menos 6 caracteres.")

    with SessionLocal() as db:
        organizacoes = (
            db.query(Organizacao)
            .order_by(Organizacao.organizacao_id.asc())
            .all()
        )
        if not organizacoes:
            raise SystemExit("Nenhuma organizacao encontrada.")

        senha_hash = hash_senha(senha)
        criados = 0
        atualizados = 0
        total_lojas = 0

        try:
            for organizacao in organizacoes:
                lojas = (
                    db.query(Loja)
                    .filter(Loja.organizacao_id == organizacao.organizacao_id)
                    .order_by(Loja.loja_id.asc())
                    .all()
                )
                total_lojas += len(lojas)
                usuarios_desejados = [
                    (cargo, None) for cargo in CARGOS_SEM_LOJA
                ]
                usuarios_desejados.extend(
                    (cargo, loja)
                    for loja in lojas
                    for cargo in CARGOS_COM_LOJA
                )

                for cargo, loja in usuarios_desejados:
                    loja_id = loja.loja_id if loja is not None else None
                    email = _email(organizacao.organizacao_id, cargo, loja_id)
                    usuario = (
                        db.query(Usuario)
                        .filter(Usuario.emailuser == email)
                        .first()
                    )
                    if usuario is None and loja is not None:
                        email_anterior = _email(
                            organizacao.organizacao_id,
                            cargo,
                        )
                        usuario = (
                            db.query(Usuario)
                            .filter(Usuario.emailuser == email_anterior)
                            .first()
                        )
                    if usuario is None:
                        usuario = Usuario(emailuser=email)
                        db.add(usuario)
                        criados += 1
                    else:
                        usuario.emailuser = email
                        atualizados += 1

                    usuario.organizacao_id = organizacao.organizacao_id
                    usuario.loja_id = loja_id
                    usuario.nmusuario = (
                        f"Teste {cargo} - {organizacao.nmorganizacao}"
                        if loja is None
                        else f"Teste {cargo} - {loja.nmloja}"
                    )
                    usuario.senhahashuser = senha_hash
                    usuario.dscargo = cargo
                    usuario.situsuario = "ATIVO"

            db.commit()
        except Exception:
            db.rollback()
            raise

        print(
            f"Concluido: {criados} usuario(s) criado(s) e "
            f"{atualizados} atualizado(s) em {len(organizacoes)} organizacao(oes) "
            f"e {total_lojas} loja(s)."
        )
        print(f"Senha comum: {senha}")
        print("Sem loja: teste.<cargo>.org<organizacao_id>@clubbar.local")
        print(
            "Com loja: "
            "teste.<cargo>.org<organizacao_id>.loja<loja_id>@clubbar.local"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
