# app/routers/pagamentos.py
from __future__ import annotations
import json
import traceback
import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from contextlib import nullcontext

from app.database import get_db
from app.schemas.pagamentos import PagarNovoIn
from app.models.carrinho import Carrinho
from app.models.venda import Venda
from app.models.produto import Produto
from app.models.pagvenda import PagVenda
from app.models.cliente import Cliente

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
from app.services.stripe_service import criar_checkout_stripe

from app.services.asaas_service import (
    obter_ou_criar_customer_asaas,
    criar_checkout_asaas,
    criar_cobranca_pix_asaas,
    buscar_qrcode_pix_asaas,
)

from app.models.checkout_asaas import CheckoutAsaas

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
                "nmparticipante": it.get("nmparticipante"),
                "cpfparticipante": it.get("cpfparticipante"),
            }
        )

    return itens_recalculados, total

def db_tx(db: Session):
    return nullcontext() if db.in_transaction() else db.begin()

@router.post("/pagar-novo")
async def pagar_novo(payload: PagarNovoIn, db: Session = Depends(get_db)):

    metodo = (payload.dsmetodopag or "PIX").strip().upper()

    try:
        
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

        cliente = get_cliente(db, payload.cliente_id)

        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")

        carrinho_id = int(carrinho.get("carrinho_id") or 0)

        if carrinho_id == 0:
            raise HTTPException(status_code=400, detail="Carrinho inválido")

        if metodo == "PIX":
            carrinho_db = (
                db.query(Carrinho)
                .filter(Carrinho.carrinho_id == carrinho_id)
                .first()
            )

            if not carrinho_db:
                raise HTTPException(status_code=404, detail="Carrinho não encontrado")

            valor_atual = round(float(total_recalculado or 0), 2)
            valor_pix_salvo = round(float(carrinho_db.vrpixmercadopago or 0), 2)

            if carrinho_db.idpixmercadopago and valor_pix_salvo == valor_atual:
                pagamento = await consultar_pagamento(
                    str(carrinho_db.idpixmercadopago)
                )

                status_mp = (pagamento.get("status") or "").lower()

                if status_mp in ["pending", "in_process"]:
                    transaction_data = (
                        pagamento.get("point_of_interaction", {})
                        .get("transaction_data", {})
                    )

                    return {
                        "venda_id": None,
                        "carrinho_id": carrinho_id,
                        "pagamento_id": pagamento.get("id"),
                        "status": "PENDENTE",
                        "metodo": "PIX",
                        "pix_copia_cola": transaction_data.get("qr_code", ""),
                        "qr_code_base64": transaction_data.get("qr_code_base64", ""),
                        "ticket_url": transaction_data.get("ticket_url", ""),
                        "reutilizado": True,
                    }

            data = await criar_pagamento_pix(
                valor=valor_atual,
                descricao=f"Carrinho {carrinho_id} - Clubbar",
                email=cliente.get("email"),
                nome=cliente.get("nome"),
                cpf=cliente.get("cpf"),
                venda_id=0,
                external_reference=f"CARRINHO-{carrinho_id}",
            )

            with db_tx(db):
                carrinho_db = (
                    db.query(Carrinho)
                    .filter(Carrinho.carrinho_id == carrinho_id)
                    .with_for_update()
                    .first()
                )

                if not carrinho_db:
                    raise HTTPException(status_code=404, detail="Carrinho não encontrado")

                carrinho_db.idpixmercadopago = str(data.get("id"))
                carrinho_db.vrpixmercadopago = valor_atual

            point = data.get("point_of_interaction") or {}
            transaction_data = point.get("transaction_data") or {}

            return {
                "venda_id": None,
                "carrinho_id": carrinho_id,
                "pagamento_id": data.get("id"),
                "status": "PENDENTE",
                "metodo": "PIX",
                "pix_copia_cola": transaction_data.get("qr_code", ""),
                "qr_code_base64": transaction_data.get("qr_code_base64", ""),
                "ticket_url": transaction_data.get("ticket_url", ""),
                "reutilizado": False,
            }
        # >>>>> fim do if == pix >>>>>>>>>

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
            descricao=f"Compra Clubbar - Carrinho {carrinho_id}",
            email=cliente.get("email"),
            nome=cliente.get("nome"),
            cpf=cliente.get("cpf"),
            external_reference=f"CARRINHO-{carrinho_id}",
            card_token=payload.card_token,
            payment_method_id=payload.payment_method_id,
            issuer_id=payload.issuer_id,
            installments=payload.installments or 1,
            tipo_pagamento=tipo_mp,
            device_id=payload.device_id,
            idempotency_key=minha_chave,
        )

        status_mp = (data.get("status") or "").upper()

        if status_mp == "APPROVED":
            status_local = "PAGO"
        elif status_mp == "REJECTED":
            status_local = "RECUSADO"
        else:
            status_local = "PENDENTE"

        return {
            "venda_id": None,
            "carrinho_id": carrinho_id,
            "pagamento_id": data.get("id"),
            "status": status_local,
            "status_mp": data.get("status"),
            "status_detail": data.get("status_detail"),
            "metodo": metodo,
            "aguardando_webhook": status_mp == "APPROVED",
            "baixa": None,
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



@router.post("/pagar-asaas")
async def pagar_asaas(
    payload: PagarNovoIn,
    db: Session = Depends(get_db),
):
    try:
        carrinho = get_carrinho(db, payload.cliente_id, payload.loja_id)

        if not carrinho:
            raise HTTPException(status_code=404, detail="Carrinho não encontrado")

        itens = carrinho.get("itens") or []

        if not itens:
            raise HTTPException(status_code=400, detail="Carrinho vazio")

        itens_recalculados, total_recalculado = _recalcular_itens_carrinho(db, itens)

        carrinho_id = int(carrinho.get("carrinho_id") or 0)

        if carrinho_id == 0:
            raise HTTPException(status_code=400, detail="Carrinho inválido")

        cliente = (
            db.query(Cliente)
            .filter(Cliente.cliente_id == payload.cliente_id)
            .first()
        )

        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")

        external_reference = f"CARRINHO-{carrinho_id}"

        checkout_existente = (
            db.query(CheckoutAsaas)
            .filter(CheckoutAsaas.carrinho_id == carrinho_id)
            .filter(CheckoutAsaas.status.in_(["ACTIVE", "PENDING"]))
            .order_by(CheckoutAsaas.checkout_asaas_id.desc())
            .first()
        )

        if checkout_existente:
            return {
                "ok": True,
                "gateway": "ASAAS",
                "carrinho_id": carrinho_id,
                "pagamento_id": checkout_existente.checkout_id,
                "status": checkout_existente.status,
                "checkout_url": checkout_existente.checkout_url,
                "external_reference": checkout_existente.external_reference,
                "reutilizado": True,
            }

        pagamento = await criar_checkout_asaas(
            valor=total_recalculado,
            descricao=f"Compra Clubbar - Carrinho {carrinho_id}",
            external_reference=external_reference,
            carrinho_id=carrinho_id,
            nome_cliente=cliente.nmcliente,
            email_cliente=cliente.emailcliente,
            cpf_cliente=cliente.nrcpfcliente,
            celular_cliente=cliente.nrtelcliente,
        )

        checkout_id = pagamento.get("id")
        checkout_url = pagamento.get("link")
        status = pagamento.get("status") or "ACTIVE"

        if not checkout_id or not checkout_url:
            raise HTTPException(
                status_code=500,
                detail={
                    "erro": "Asaas não retornou id ou link do checkout.",
                    "asaas_response": pagamento,
                },
            )

        novo = CheckoutAsaas(
            carrinho_id=carrinho_id,
            cliente_id=payload.cliente_id,
            loja_id=payload.loja_id,
            checkout_id=checkout_id,
            checkout_url=checkout_url,
            external_reference=external_reference,
            status=status,
        )

        db.add(novo)
        db.commit()

        return {
            "ok": True,
            "gateway": "ASAAS",
            "carrinho_id": carrinho_id,
            "pagamento_id": checkout_id,
            "status": status,
            "checkout_url": checkout_url,
            "external_reference": external_reference,
            "reutilizado": False,
        }

    except HTTPException:
        raise

    except Exception as e:
        print("[ASAAS][ERRO]", repr(e))
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar pagamento Asaas ({type(e).__name__}): {e}",
        )