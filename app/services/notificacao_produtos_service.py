"""Notificações de produto enviadas após a confirmação da venda."""

from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.produto import Produto
from app.models.venda import Venda
from app.services.email_service import enviar_produtos_confirmados
from app.services.ingresso_qrcode_service import dados_qr_produto
from app.services.public_urls import url_api_publica


def enviar_produtos_confirmados_da_venda(db: Session, venda_id: int) -> bool:
    """Envia, em uma única mensagem, os QR Codes dos produtos da venda."""
    registros = (
        db.query(ItVenda, Cliente, Loja, Produto)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Cliente, Cliente.cliente_id == Venda.cliente_id)
        .join(Loja, Loja.loja_id == Venda.loja_id)
        .outerjoin(Produto, Produto.produto_id == ItVenda.produto_id)
        .filter(
            ItVenda.venda_id == venda_id,
            ItVenda.tipoitem == "PRODUTO",
            ItVenda.sititvenda == "ATIVO",
            Venda.sitvenda == "PAGA",
        )
        .order_by(ItVenda.itvenda_id)
        .all()
    )
    if not registros:
        return False

    _, cliente, _, _ = registros[0]
    if not (cliente.emailcliente or "").strip():
        return False

    base_url = url_api_publica()
    produtos: list[dict[str, str]] = []
    for item, _, loja, produto in registros:
        token = (item.qrtokenitvenda or "").strip()
        if not token:
            continue
        produtos.append(
            {
                "produto": produto.nmproduto if produto else "Produto Clubbar",
                "loja": loja.nmloja or "Estabelecimento Clubbar",
                "qr_url": f"{base_url}/publico/produtos/{token}/qr.png",
                "dados_qr": dados_qr_produto(token),
            }
        )

    if not produtos:
        return False
    enviar_produtos_confirmados(
        destinatario=cliente.emailcliente.strip(),
        nome_cliente=cliente.nmcliente or "cliente",
        produtos=produtos,
    )
    return True
