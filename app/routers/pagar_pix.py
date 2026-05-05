from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime
import requests
import uuid
import os

from app.database import get_db
from app.models.cliente import Cliente
from app.models.produto import Produto
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])

PAGBANK_TOKEN = os.getenv("PAGBANK_TOKEN")

class PagarPixRequest(BaseModel):
    cliente_id: int
    organizacao_id: int
    loja_id: int

@router.post("/pagar-pix")
async def pagar_pix(
    payload: PagarPixRequest,
    db: Session = Depends(get_db),
):
    try:
        cliente_id = payload.cliente_id
        organizacao_id = payload.organizacao_id
        loja_id = payload.loja_id

        if not cliente_id:
            raise HTTPException(400, "cliente_id obrigatório")

        # 🔎 cliente
        cliente = db.query(Cliente).filter(
            Cliente.cliente_id == cliente_id
        ).first()

        if not cliente:
            raise HTTPException(404, "Cliente não encontrado")

        # 🔎 pegar itens do carrinho (simplificado — adapte se já tiver função)
        carrinho_itens = db.execute("""
            SELECT produto_id, qtitcarrinho
            FROM itcarrinho
            WHERE carrinho_id = (
                SELECT carrinho_id FROM carrinho
                WHERE cliente_id = :cliente_id AND loja_id = :loja_id
                ORDER BY carrinho_id DESC LIMIT 1
            )
        """, {"cliente_id": cliente_id, "loja_id": loja_id}).fetchall()

        if not carrinho_itens:
            raise HTTPException(400, "Carrinho vazio")

        total = 0
        itens_venda = []

        for item in carrinho_itens:
            produto = db.query(Produto).filter(
                Produto.produto_id == item.produto_id
            ).first()

            preco = float(produto.vrprecoprod or 0)
            qt = int(item.qtitcarrinho or 1)

            total += preco * qt

            itens_venda.append({
                "produto": produto,
                "qt": qt,
                "preco": preco
            })

        # 💾 cria VENDA
        venda = Venda(
            cliente_id=cliente_id,
            organizacao_id=organizacao_id,
            loja_id=loja_id,
            dtvenda=datetime.now(),
            sitvenda="PENDENTE"
        )

        db.add(venda)
        db.flush()  # 🔥 pega venda_id

        # 💾 itens
        for it in itens_venda:
            db.add(ItVenda(
                venda_id=venda.venda_id,
                produto_id=it["produto"].produto_id,
                qtitvenda=it["qt"],
                vrunitvenda=it["preco"]
            ))

        # 💾 pagamento
        pag = PagVenda(
            venda_id=venda.venda_id,
            sitpagvenda="PENDENTE",
            dtpagvenda=datetime.now()
        )
        db.add(pag)

        db.commit()

        # =========================
        # 🔥 PAGBANK PIX
        # =========================

        payload_pagbank = {
            "reference_id": f"VENDA-{venda.venda_id}",
            "customer": {
                "name": cliente.nmcliente or "Cliente",
                "email": cliente.emailcliente,
                "tax_id": getattr(cliente, "cpfcliente", "12345678909")
            },
            "items": [
                {
                    "name": it["produto"].nmproduto,
                    "quantity": it["qt"],
                    "unit_amount": int(it["preco"] * 100)
                }
                for it in itens_venda
            ],
            "qr_codes": [
                {
                    "amount": {
                        "value": int(total * 100)
                    }
                }
            ],
            "notification_urls": [
                "https://bitbeer-production.up.railway.app/pagamentos/webhook"
            ]
        }

        headers = {
            "Authorization": f"Bearer {PAGBANK_TOKEN}",
            "Content-Type": "application/json"
        }

        resp = requests.post(
            "https://api.pagseguro.com/orders",
            json=payload_pagbank,
            headers=headers
        )

        if resp.status_code not in [200, 201]:
            print("[PIX] ERRO PAGBANK:", resp.text)
            raise HTTPException(400, resp.text)

        data = resp.json()

        # 🔎 pegar QR Code
        qr = data.get("qr_codes", [{}])[0]
        qr_text = qr.get("text")
        qr_base64 = qr.get("links", [{}])[0].get("href")

        return {
            "venda_id": venda.venda_id,
            "status": "PENDENTE",
            "total": total,
            "qr_code": qr_text,
            "qr_code_url": qr_base64
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Erro no PIX: {e}")