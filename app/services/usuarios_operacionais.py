import re
import unicodedata


def iniciais_loja(nome: str) -> str:
    texto = unicodedata.normalize("NFKD", nome or "")
    texto = "".join(c for c in texto if not unicodedata.combining(c)).lower()
    palavras = re.findall(r"[a-z0-9]+", texto)
    principais = [p for p in palavras if p not in {"de", "da", "do", "das", "dos", "e"}]
    iniciais = "".join(p[0] for p in principais or palavras)
    if not iniciais:
        raise ValueError("O nome da loja não permite gerar usuários operacionais.")
    return iniciais


PERFIS_PADRAO = (
    ("b1", "BARMAN", "Barman 1"),
    ("b2", "BARMAN", "Barman 2"),
    ("tk1", "TICKETMAN", "Ticketman 1"),
    ("m1", "MOTOBOY", "Motoboy 1"),
)


def dominio_disponivel(nome, loja_id, email_em_uso):
    iniciais = iniciais_loja(nome)
    for sufixo in ("", str(loja_id)):
        dominio = f"{iniciais}{sufixo}.com"
        if all(not email_em_uso(f"{prefixo}@{dominio}") for prefixo, _, _ in PERFIS_PADRAO):
            return dominio
    raise ValueError("Não foi possível gerar logins únicos para esta loja.")
