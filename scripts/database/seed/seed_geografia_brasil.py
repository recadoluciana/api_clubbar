from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import gzip
from typing import Any

from sqlalchemy import text

# Permite executar:
#   python database/seed/seed_geografia_brasil.py
# a partir da raiz do projeto api_clubbar.
from app.database import SessionLocal


IBGE_ESTADOS_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados"
IBGE_MUNICIPIOS_UF_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf_id}/municipios"
)

PAIS_CODIGO = 76
PAIS_NOME = "Brasil"
PAIS_SIGLA = "BR"


import gzip


def buscar_json(url: str) -> list[dict[str, Any]]:
    """Busca uma lista JSON na API do IBGE."""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Clubbar-Seed-Geografia/1.0",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            conteudo = response.read()

            if response.headers.get("Content-Encoding") == "gzip":
                conteudo = gzip.decompress(conteudo)

            charset = response.headers.get_content_charset() or "utf-8"
            texto = conteudo.decode(charset)

            dados = json.loads(texto)

            if not isinstance(dados, list):
                raise RuntimeError(
                    f"Resposta inesperada da API para {url}"
                )

            return dados

    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"Erro HTTP {exc.code} ao consultar o IBGE: {url}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Não foi possível acessar a API do IBGE: "
            f"{url}. Erro: {exc.reason}"
        ) from exc

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"A API do IBGE retornou JSON inválido: {url}"
        ) from exc

def obter_ou_criar_pais(db) -> int:
    db.execute(
        text(
            """
            INSERT INTO pais (cdpais, nmpais, sgpais)
            VALUES (:cdpais, :nmpais, :sgpais)
            ON DUPLICATE KEY UPDATE
                nmpais = VALUES(nmpais),
                sgpais = VALUES(sgpais)
            """
        ),
        {
            "cdpais": PAIS_CODIGO,
            "nmpais": PAIS_NOME,
            "sgpais": PAIS_SIGLA,
        },
    )

    pais_id = db.execute(
        text(
            """
            SELECT pais_id
            FROM pais
            WHERE cdpais = :cdpais
            LIMIT 1
            """
        ),
        {"cdpais": PAIS_CODIGO},
    ).scalar_one()

    return int(pais_id)


def obter_ou_criar_estado(
    db,
    *,
    pais_id: int,
    cdibge: int,
    sigla: str,
    nome: str,
) -> int:
    # Como cdibge é UNIQUE, usamos o código oficial do IBGE como chave estável.
    db.execute(
        text(
            """
            INSERT INTO estado (
                pais_id,
                cdibge,
                sgestado,
                nmestado
            )
            VALUES (
                :pais_id,
                :cdibge,
                :sgestado,
                :nmestado
            )
            ON DUPLICATE KEY UPDATE
                pais_id = VALUES(pais_id),
                sgestado = VALUES(sgestado),
                nmestado = VALUES(nmestado)
            """
        ),
        {
            "pais_id": pais_id,
            "cdibge": cdibge,
            "sgestado": sigla,
            "nmestado": nome,
        },
    )

    estado_id = db.execute(
        text(
            """
            SELECT estado_id
            FROM estado
            WHERE cdibge = :cdibge
            LIMIT 1
            """
        ),
        {"cdibge": cdibge},
    ).scalar_one()

    return int(estado_id)


def inserir_ou_atualizar_cidade(
    db,
    *,
    pais_id: int,
    estado_id: int,
    cdibge: int,
    nome: str,
) -> None:
    # cdibge também é UNIQUE na sua tabela cidade.
    db.execute(
        text(
            """
            INSERT INTO cidade (
                pais_id,
                estado_id,
                nmcidade,
                cdibge
            )
            VALUES (
                :pais_id,
                :estado_id,
                :nmcidade,
                :cdibge
            )
            ON DUPLICATE KEY UPDATE
                pais_id = VALUES(pais_id),
                estado_id = VALUES(estado_id),
                nmcidade = VALUES(nmcidade)
            """
        ),
        {
            "pais_id": pais_id,
            "estado_id": estado_id,
            "nmcidade": nome,
            "cdibge": cdibge,
        },
    )


def main() -> None:
    print("=" * 72)
    print("CLUBBAR - SEED DE PAÍS, ESTADOS E MUNICÍPIOS DO BRASIL")
    print("Fonte: API de Localidades do IBGE")
    print("=" * 72)

    print("\n[1/3] Consultando Unidades da Federação no IBGE...")
    estados = buscar_json(IBGE_ESTADOS_URL)
    estados = sorted(estados, key=lambda item: int(item["id"]))

    db = SessionLocal()

    total_estados = 0
    total_cidades = 0

    try:
        print("[2/3] Gravando o país Brasil...")
        pais_id = obter_ou_criar_pais(db)
        db.commit()

        print(f"      Brasil gravado/encontrado com pais_id={pais_id}")

        print("\n[3/3] Gravando estados e municípios...")

        for estado in estados:
            uf_ibge = int(estado["id"])
            uf_sigla = str(estado["sigla"]).strip()
            uf_nome = str(estado["nome"]).strip()

            try:
                estado_id = obter_ou_criar_estado(
                    db,
                    pais_id=pais_id,
                    cdibge=uf_ibge,
                    sigla=uf_sigla,
                    nome=uf_nome,
                )
                db.commit()

                url_municipios = IBGE_MUNICIPIOS_UF_URL.format(uf_id=uf_ibge)
                municipios = buscar_json(url_municipios)
                municipios = sorted(municipios, key=lambda item: int(item["id"]))

                for municipio in municipios:
                    inserir_ou_atualizar_cidade(
                        db,
                        pais_id=pais_id,
                        estado_id=estado_id,
                        cdibge=int(municipio["id"]),
                        nome=str(municipio["nome"]).strip(),
                    )

                db.commit()

                total_estados += 1
                total_cidades += len(municipios)

                print(
                    f"      [{uf_sigla}] {uf_nome}: "
                    f"{len(municipios)} município(s) gravado(s)."
                )

            except Exception:
                db.rollback()
                raise

        print("\n" + "=" * 72)
        print("SEED CONCLUÍDO COM SUCESSO")
        print(f"País:          {PAIS_NOME}")
        print(f"Estados/UFs:   {total_estados}")
        print(f"Municípios:    {total_cidades}")
        print("=" * 72)

        # Validação final usando o próprio banco.
        resultado = db.execute(
            text(
                """
                SELECT
                    (SELECT COUNT(*) FROM pais WHERE cdpais = :cdpais) AS qtd_pais,
                    (SELECT COUNT(*)
                       FROM estado e
                      WHERE e.pais_id = :pais_id) AS qtd_estados,
                    (SELECT COUNT(*)
                       FROM cidade c
                      WHERE c.pais_id = :pais_id) AS qtd_cidades
                """
            ),
            {
                "cdpais": PAIS_CODIGO,
                "pais_id": pais_id,
            },
        ).mappings().one()

        print("\nValidação no banco:")
        print(f"  Brasil encontrado: {resultado['qtd_pais']}")
        print(f"  Estados cadastrados: {resultado['qtd_estados']}")
        print(f"  Cidades cadastradas: {resultado['qtd_cidades']}")

    except Exception as exc:
        db.rollback()
        print("\nERRO AO EXECUTAR O SEED:")
        print(str(exc))
        sys.exit(1)

    finally:
        db.close()


if __name__ == "__main__":
    main()
