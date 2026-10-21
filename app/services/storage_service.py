"""Armazenamento de uploads com fallback local para desenvolvimento.

As URLs públicas continuam sendo ``/uploads/<chave>``. Em produção, a API
faz o proxy de leitura do bucket privado, evitando expor credenciais ao app.
"""

from __future__ import annotations

import io
import mimetypes
from pathlib import Path, PurePosixPath
from typing import BinaryIO

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from app.core.config import (
    STORAGE_S3_ACCESS_KEY_ID,
    STORAGE_S3_ADDRESSING_STYLE,
    STORAGE_S3_BUCKET,
    STORAGE_S3_ENDPOINT,
    STORAGE_S3_REGION,
    STORAGE_S3_SECRET_ACCESS_KEY,
    UPLOAD_DIR,
)


def armazenamento_remoto_habilitado() -> bool:
    return all(
        (
            STORAGE_S3_ENDPOINT,
            STORAGE_S3_ACCESS_KEY_ID,
            STORAGE_S3_SECRET_ACCESS_KEY,
            STORAGE_S3_BUCKET,
        )
    )


def _cliente_s3():
    if not armazenamento_remoto_habilitado():
        return None
    estilo_enderecamento = {
        "virtual-host": "virtual",
        "virtual_host": "virtual",
    }.get(STORAGE_S3_ADDRESSING_STYLE.lower(), STORAGE_S3_ADDRESSING_STYLE.lower())
    return boto3.client(
        "s3",
        endpoint_url=STORAGE_S3_ENDPOINT,
        aws_access_key_id=STORAGE_S3_ACCESS_KEY_ID,
        aws_secret_access_key=STORAGE_S3_SECRET_ACCESS_KEY,
        region_name=STORAGE_S3_REGION,
        config=Config(s3={"addressing_style": estilo_enderecamento}),
    )


def normalizar_chave(chave: str) -> str:
    caminho = PurePosixPath(chave.lstrip("/"))
    if not chave or caminho.is_absolute() or ".." in caminho.parts:
        raise ValueError("Caminho de upload inválido.")
    return caminho.as_posix()


def salvar_arquivo(chave: str, arquivo: BinaryIO, content_type: str | None = None) -> str:
    chave = normalizar_chave(chave)
    cliente = _cliente_s3()
    if cliente is not None:
        if hasattr(arquivo, "seek"):
            arquivo.seek(0)
        parametros = {"Bucket": STORAGE_S3_BUCKET, "Key": chave, "Body": arquivo}
        if content_type:
            parametros["ContentType"] = content_type
        cliente.put_object(**parametros)
    else:
        destino = UPLOAD_DIR / chave
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("wb") as saida:
            while bloco := arquivo.read(1024 * 1024):
                saida.write(bloco)
    return f"/uploads/{chave}"


def salvar_bytes(chave: str, conteudo: bytes, content_type: str | None = None) -> str:
    return salvar_arquivo(chave, io.BytesIO(conteudo), content_type)


def obter_arquivo(chave: str) -> tuple[bytes, str] | None:
    """Retorna o objeto remoto; durante a migração tenta o volume como fallback."""
    chave = normalizar_chave(chave)
    cliente = _cliente_s3()
    if cliente is not None:
        try:
            resposta = cliente.get_object(Bucket=STORAGE_S3_BUCKET, Key=chave)
            tipo = resposta.get("ContentType") or mimetypes.guess_type(chave)[0]
            return resposta["Body"].read(), tipo or "application/octet-stream"
        except ClientError as erro:
            codigo = str(erro.response.get("Error", {}).get("Code", ""))
            if codigo not in {"NoSuchKey", "404", "NotFound"}:
                raise

    caminho_local = UPLOAD_DIR / chave
    if not caminho_local.is_file():
        return None
    return caminho_local.read_bytes(), (
        mimetypes.guess_type(chave)[0] or "application/octet-stream"
    )
