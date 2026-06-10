# app/routers/pagamentos.py
from __future__ import annotations

import traceback
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pagamentos import PagarNovoIn
from app.models.venda import Venda
from app.models.produto import Produto
from app.models.pagvenda import PagVenda

from app.services.carrinho_service import get_carrinho
from app.services.venda_service import criar_ou_obter_venda_idempotente
from app.services.cliente_service import get_cliente
from app.services.mercadopago_service import (
    criar_pagamento_pix,
    criar_pagamento_cartao_mp,
    consultar_pagamento,
 )

from app.services.pagamento_status_service import set_venda_como_paga

from app.routers.produtos import calcular_preco_final

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])


def _recalcular_itens_carrinho(
    db: Session,
    itens: list[Dict[str, Any]],
) -> tuple[list[Dict[str, Any]], float]:
    itens_recalculados = []
    total = 0.0

    for it in itens:
        produto_id = int(it.get("produto_id") or 0)
        qt = int(it.get("qt") or it.get("qtitcarrinho") or 1)

        produto = db.query(Produto).filter(
            Produto.produto_id == produto_id
        ).first()

        if not produto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produto {produto_id} não encontrado",
            )

        if (produto.sitproduto or "").upper() != "ATIVO":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produto '{produto.nmproduto}' não está disponível",
            )

        vrprecofinal, descontoativo = calcular_preco_final(produto)
        vrunitario = float(vrprecofinal)
        subtotal = vrunitario * qt
        total += subtotal

        itens_recalculados.append(
            {
                "produto_id": produto.produto_id,
                "nmproduto": produto.nmproduto,
                "qt": qt,
                "qtitcarrinho": qt,
                "vrunitario": vrunitario,
                "subtotal": subtotal,
                "tipodesconto": produto.tipodesconto or "NENHUM",
                "vrdesconto": float(produto.vrdesconto or 0),
                "descontoativo": descontoativo,
                "dsobsitcar": it.get("dsobsitcar") or it.get("obs"),
            }
        )

    return itens_recalculados, total


@router.post("/pagar-novo")
async def pagar_novo(payload: PagarNovoIn, db: Session = Depends(get_db)):
    metodo = (payload.dsmetodopag or "PIX").strip().upper()

    try:
        with db.begin():
            carrinho = get_carrinho(db, payload.cliente_id, payload.loja_id)

            if not carrinho:
                raise HTTPException(status_code=404, detail="Carrinho não encontrado")

            itens = carrinho.get("itens") or []

            if not isinstance(itens, list):
                raise HTTPException(status_code=500, detail="Formato inválido dos itens do carrinho")

            if not itens:
                raise HTTPException(status_code=400, detail="Carrinho vazio")

            itens_recalculados, total_recalculado = _recalcular_itens_carrinho(
                db,
                itens,
            )

            minha_chave = payload.idempotency_key or str(uuid.uuid4())

            venda = await criar_ou_obter_venda_idempotente(
                db,
                cliente_id=payload.cliente_id,
                organizacao_id=payload.organizacao_id,
                loja_id=payload.loja_id,
                carrinho={
                    **carrinho,
                    "total": total_recalculado,
                    "itens": itens_recalculados,
                },
                chave=minha_chave,
                metodo_pagamento=metodo,
            )

            venda_id = int(venda["venda_id"])
            pagvenda_id = int(venda["pagvenda_id"])

            cliente = get_cliente(db, payload.cliente_id)

            if not cliente:
                raise HTTPException(status_code=404, detail="Cliente não encontrado")

        if metodo == "PIX":
            data = await criar_pagamento_pix(
                valor=total_recalculado,
                descricao=f"Venda {venda_id} - Clubbar",
                email=cliente.get("email"),
                nome=cliente.get("nome"),
                cpf=cliente.get("cpf"),
                venda_id=venda_id,
            )

            with db.begin():
                pag = (
                    db.query(PagVenda)
                    .filter(PagVenda.pagvenda_id == pagvenda_id)
                    .with_for_update()
                    .first()
                )

                if not pag:
                    raise HTTPException(status_code=404, detail="PagVenda não encontrada")

                pag.dsmetodopag = "PIX"
                pag.sitpagvenda = "PENDENTE"
                pag.idtransacaopagvenda = str(data.get("id"))
                pag.checkout_id = str(data.get("id"))
                pag.reference_id = str(venda_id)
                pag.pay_url = None
                pag.provedor = "MERCADO_PAGO"

            point = data.get("point_of_interaction") or {}
            transaction_data = point.get("transaction_data") or {}

            return {
                "venda_id": venda_id,
                "pagamento_id": data.get("id"),
                "status": "PENDENTE",
                "metodo": "PIX",
                "pix_copia_cola": transaction_data.get("qr_code", ""),
                "qr_code_base64": transaction_data.get("qr_code_base64", ""),
                "ticket_url": transaction_data.get("ticket_url", ""),
            }

        if metodo not in ["CREDIT_CARD", "DEBIT_CARD"]:
            raise HTTPException(
                status_code=400,
                detail="Método de pagamento inválido. Use PIX, CREDIT_CARD ou DEBIT_CARD.",
            )

        if not payload.card_token:
            raise HTTPException(
                status_code=400,
                detail="Token do cartão não informado.",
            )

        tipo_mp = "credit_card" if metodo == "CREDIT_CARD" else "debit_card"

        data = await criar_pagamento_cartao_mp(
            valor=total_recalculado,
            descricao=f"Venda {venda_id} - Clubbar",
            email=cliente.get("email"),
            nome=cliente.get("nome"),
            cpf=cliente.get("cpf"),
            venda_id=venda_id,
            card_token=payload.card_token,
            payment_method_id=payload.payment_method_id,
            issuer_id=payload.issuer_id,
            installments=payload.installments or 1,
            tipo_pagamento=tipo_mp,
            idempotency_key=minha_chave,
        )

        status_mp = (data.get("status") or "").upper()
        status_local = "PAGO" if status_mp == "APPROVED" else "PENDENTE"

        with db.begin():
            pag = (
                db.query(PagVenda)
                .filter(PagVenda.pagvenda_id == pagvenda_id)
                .with_for_update()
                .first()
            )

            if not pag:
                raise HTTPException(status_code=404, detail="PagVenda não encontrada")

            pag.dsmetodopag = metodo
            pag.sitpagvenda = status_local
            pag.idtransacaopagvenda = str(data.get("id"))
            pag.checkout_id = str(data.get("id"))
            pag.reference_id = str(venda_id)
            pag.pay_url = None
            pag.provedor = "MERCADO_PAGO"

        return {
            "venda_id": venda_id,
            "pagamento_id": data.get("id"),
            "status": status_local,
            "status_mp": data.get("status"),
            "status_detail": data.get("status_detail"),
            "metodo": metodo,
        }

    except HTTPException:
        raise

    except Exception as e:
        print("[PAGAR_NOVO][ERRO]", repr(e))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar pagamento Mercado Pago ({type(e).__name__}): {e}",
        )

@router.get("/pendente")
async def pagamento_pendente(
    cliente_id: int,
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
):
    venda = (
        db.query(Venda)
        .filter(
            Venda.cliente_id == cliente_id,
            Venda.loja_id == loja_id,
            Venda.sitvenda.in_(["PENDENTE", "PAGA"]),
        )
        .order_by(Venda.venda_id.desc())
        .first()
    )

    if not venda:
        return {"ok": True, "found": False}

    return {
        "ok": True,
        "found": True,
        "venda_id": venda.venda_id,
        "sitvenda": venda.sitvenda,
    }


@router.post("/mercadopago/consultar/{venda_id}")
async def consultar_mercadopago_por_venda(
    venda_id: int,
    db: Session = Depends(get_db),
):
    pag = (
        db.query(PagVenda)
        .filter(PagVenda.venda_id == venda_id)
        .order_by(PagVenda.pagvenda_id.desc())
        .first()
    )

    if not pag:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado")

    if not pag.idtransacaopagvenda:
        raise HTTPException(status_code=400, detail="ID do pagamento não encontrado")

    data = await consultar_pagamento(str(pag.idtransacaopagvenda))

    status_mp = (data.get("status") or "").lower()

    if status_mp == "approved":
        with db.begin():
            resultado = set_venda_como_paga(
                db,
                venda_id=venda_id,
                gateway="OUTRO",
                payload={
                    "charges": [
                        {
                            "id": str(data.get("id")),
                            "status": "PAID",
                        }
                    ],
                    "mercadopago": data,
                },
            )

        return {
            "ok": True,
            "venda_id": venda_id,
            "status": "PAGO",
            "resultado": resultado,
        }

    return {
        "ok": True,
        "venda_id": venda_id,
        "status": status_mp or "PENDENTE",
    }


@router.post("/mock-aprovar/{venda_id}")
async def mock_aprovar_pagamento(
    venda_id: int,
    db: Session = Depends(get_db),
):
    try:
        with db.begin():
            resultado = set_venda_como_paga(
                db,
                venda_id=venda_id,
                gateway="MERCADOPAGO",
                payload={
                    "id": f"MOCK_MP_{venda_id}",
                    "status": "approved",
                    "charges": [
                        {
                            "id": f"MOCK_MP_{venda_id}",
                            "status": "PAID",
                        }
                    ],
                    "mercadopago": {
                        "id": f"MOCK_MP_{venda_id}",
                        "status": "approved",
                        "external_reference": str(venda_id),
                    },
                },
            )

        return {
            "ok": True,
            "venda_id": venda_id,
            "status": "PAGO",
            "resultado": resultado,
        }

    except HTTPException:
        raise

    except Exception as e:
        print("[MOCK APROVAR][ERRO]", repr(e))
        raise HTTPException(status_code=500, detail=str(e))