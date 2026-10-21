"""Copia os uploads do volume para o bucket sem apagar a origem.

Execute dentro da API de produção enquanto o volume ainda está montado:
``python scripts/migrate_uploads_to_bucket.py``.
O script é idempotente; cada chave é regravada no bucket com o mesmo nome.
"""

from __future__ import annotations

import argparse
import mimetypes
from pathlib import Path

from app.core.config import UPLOAD_DIR
from app.services.storage_service import armazenamento_remoto_habilitado, salvar_arquivo


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not armazenamento_remoto_habilitado():
        raise SystemExit("Bucket não configurado. Defina as variáveis STORAGE_S3_*.")
    if not UPLOAD_DIR.exists():
        raise SystemExit(f"Diretório de uploads não encontrado: {UPLOAD_DIR}")

    total = 0
    tamanho = 0
    for caminho in UPLOAD_DIR.rglob("*"):
        if not caminho.is_file():
            continue
        chave = caminho.relative_to(UPLOAD_DIR).as_posix()
        total += 1
        tamanho += caminho.stat().st_size
        if not args.dry_run:
            with caminho.open("rb") as arquivo:
                salvar_arquivo(chave, arquivo, mimetypes.guess_type(chave)[0])

    acao = "PREVISTOS" if args.dry_run else "MIGRADOS"
    print(f"{acao}={total} ARQUIVOS={tamanho} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
