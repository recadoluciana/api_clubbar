"""Geração consistente do QR do ingresso para a web e para o e-mail."""

from io import BytesIO

import qrcode
from qrcode.image.svg import SvgPathImage


def dados_qr_ingresso(token: str) -> str:
    return f"CLUBBAR-INGRESSO:{token}"


def dados_qr_produto(token: str) -> str:
    """Conteúdo padronizado do QR apresentado para retirada de produtos."""
    return f"CLUBBAR-PRODUTO:{token}"


def _qr(dados: str) -> qrcode.QRCode:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(dados)
    qr.make(fit=True)
    return qr


def gerar_qr_svg(dados: str) -> str:
    imagem = _qr(dados).make_image(image_factory=SvgPathImage)
    svg = imagem.to_string(encoding="unicode")
    return svg.replace("<svg ", "<svg role='img' aria-label='QR Code do ingresso' ", 1)


def gerar_qr_png(dados: str) -> bytes:
    """PNG anexável para a pessoa salvar no celular antes de chegar ao evento."""
    imagem = _qr(dados).make_image(fill_color="black", back_color="white")
    arquivo = BytesIO()
    imagem.save(arquivo, format="PNG")
    return arquivo.getvalue()
