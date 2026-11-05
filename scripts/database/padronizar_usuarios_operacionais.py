"""Prévia por padrão; --aplicar atualiza usuários operacionais em uma transação."""
import argparse
import os
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sqlalchemy import create_engine, text
from app.core.security import hash_senha
from app.services.usuarios_operacionais import PERFIS_PADRAO, iniciais_loja


def legado(nome):
    nome = unicodedata.normalize("NFKD", nome)
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in nome if not unicodedata.combining(c)).lower())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    url = (os.environ.get("MYSQL_PUBLIC_URL") or os.environ["DATABASE_URL"]).replace("mysql://", "mysql+pymysql://", 1)
    engine = create_engine(url)
    with engine.begin() as conn:
        lojas = conn.execute(text("SELECT loja_id, organizacao_id, nmloja FROM loja ORDER BY loja_id")).mappings().all()
        usuarios = conn.execute(text("SELECT usuario_id, organizacao_id, loja_id, nmusuario, emailuser, dscargo FROM usuario")).mappings().all()
        emails = {str(u["emailuser"]).lower(): u for u in usuarios}
        for loja in lojas:
            loja_id = loja["loja_id"]
            nome = loja["nmloja"]
            antigos = {p: emails.get(f"{p}{legado(nome)}@clubbar.com.br") for p in ("barman", "ticketman")}
            antigos = {k: u for k, u in antigos.items() if u and u["loja_id"] == loja_id and u["organizacao_id"] == loja["organizacao_id"] and u["dscargo"] == k.upper()}
            iniciais = iniciais_loja(nome)
            dominio = None
            for sufixo in ("", str(loja_id)):
                candidato = f"{iniciais}{sufixo}.com"
                candidatos = [emails.get(f"{p}@{candidato}") for p, _, _ in PERFIS_PADRAO]
                if all(u is None or (u["loja_id"] == loja_id and u["organizacao_id"] == loja["organizacao_id"]) for u in candidatos):
                    dominio = candidato
                    break
            if dominio is None:
                raise RuntimeError(f"Conflito de logins na loja {loja_id}; nenhuma alteração foi aplicada.")
            for prefixo, cargo, descricao in PERFIS_PADRAO:
                email = f"{prefixo}@{dominio}"
                existente = emails.get(email)
                antigo = antigos.get({"b1": "barman", "tk1": "ticketman"}.get(prefixo, ""))
                if existente:
                    if existente["dscargo"] != cargo:
                        raise RuntimeError(f"Login {email} pertence a outro cargo; nenhuma alteração foi aplicada.")
                    continue
                if antigo:
                    print(f"Loja {loja_id}: alterar {antigo['emailuser']} para {email}")
                    if args.aplicar:
                        conn.execute(text("UPDATE usuario SET emailuser=:email WHERE usuario_id=:id"), {"email": email, "id": antigo["usuario_id"]})
                else:
                    print(f"Loja {loja_id}: criar {email} ({cargo})")
                    if args.aplicar:
                        conn.execute(text("INSERT INTO usuario (organizacao_id, loja_id, nmusuario, emailuser, senhahashuser, dscargo, situsuario) VALUES (:org, :loja, :nome, :email, :senha, :cargo, 'ATIVO')"), {"org": loja["organizacao_id"], "loja": loja_id, "nome": f"{descricao} - {nome}", "email": email, "senha": hash_senha("101010"), "cargo": cargo})
                emails[email] = {"loja_id": loja_id, "organizacao_id": loja["organizacao_id"], "dscargo": cargo}
        print("Alterações aplicadas." if args.aplicar else "Prévia: nenhuma alteração aplicada.")


if __name__ == "__main__":
    main()
