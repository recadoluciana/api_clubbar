"""Imagem pública, não indexável, do QR Code de retirada de um produto."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.itvenda import ItVenda
from app.models.venda import Venda
from app.services.ingresso_qrcode_service import dados_qr_produto, gerar_qr_png


router = APIRouter(prefix="/publico/produtos", tags=["Produtos públicos"])


@router.get("/{token}/qr.png")
def baixar_qr_produto(token: str, db: Session = Depends(get_db)):
    """Retorna o QR de um produto pago e ainda não retirado.

    O token opaco é aleatório; a rota não expõe nome, e-mail ou outros dados
    do cliente. O anexo PNG do e-mail continua disponível offline.
    """
    if len(token) < 24:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    item = (
        db.query(ItVenda)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(
            ItVenda.qrtokenitvenda == token,
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.sititvenda == "ATIVO",
            ItVenda.identregaitvenda != "SIM",
            Venda.sitvenda == "PAGA",
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Produto não encontrado.")

    return Response(
        content=gerar_qr_png(dados_qr_produto(item.qrtokenitvenda)),
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=86400",
            "X-Robots-Tag": "noindex, nofollow",
        },
    )
