# app/routers/pagamentos.py
from __future__ import annotations

import traceback
import uuid
from typing import Any, Dict
from contextlib import nullcontext

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pagamentos import PagarNovoIn

from app.models.carrinho import Carrinho
from app.models.venda import Venda
from app.models.produto import Produto
from app.models.eventolote import EventoLote
from app.models.cliente import Cliente
from app.models.checkout_asaas import CheckoutAsaas

from app.services.carrinho_service import get_carrinho
from app.services.cliente_service import get_cliente
from app.services.mercadopago_service import (
    criar_pagamento_pix,
    criar_pagamento_cartao_mp,
    consultar_pagamento,
)
from app.routers.produtos import calcular_preco_final

from app.services.asaas_service import (
    obter_ou_criar_customer_asaas,
    criar_checkout_asaas,
    sincronizar_cliente_com_asaas_se_precisar,
)

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])


def db_tx(db: Session):
    return nullcontext() if db.in_transaction() else db.begin()


def _recalcular_itens_carrinho(
    db: Session,
    itens: list[Dict[str, Any]],
    percentual_taxa_ingresso: float = 0.0,
) -> tuple[list[Dict[str, Any]], float]:
    itens_recalculados = []
    total = 0.0

    percentual_taxa_ingresso = float(percentual_taxa_ingresso or 0)

    for it in itens:
        tipo = (it.get("idtipoproduto") or "P").upper()
        qt = int(it.get("qt") or it.get("qtitcarrinho") or 1)

        produto_id = it.get("produto_id")
        lote_id = it.get("lote_id")

        if tipo == "I":
            lote_id_int = int(lote_id or 0)

            lote = (
                db.query(EventoLote)
                .filter(EventoLote.lote_id == lote_id_int)
                .first()
            )

            if not lote:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Lote {lote_id_int} não encontrado",
                )

            if (lote.statuslote or "").upper() != "ATIVO":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Lote '{lote.nmlote}' não está disponível",
                )

            vrunitario = round(float(lote.vrprecolote or 0), 2)
            subtotal = round(vrunitario * qt, 2)

            vrtaxaing = round(subtotal * (percentual_taxa_ingresso / 100), 2)
            total_com_taxa = round(subtotal + vrtaxaing, 2)

            total += total_com_taxa

            itens_recalculados.append(
                {
                    "produto_id": None,
                    "lote_id": lote.lote_id,
                    "idtipoproduto": "I",
                    "nmproduto": f"Ingresso {lote.nmlote}",
                    "qt": qt,
                    "qtitcarrinho": qt,
                    "vrunitario": vrunitario,
                    "subtotal": subtotal,
                    "percentual_taxa_ingresso": percentual_taxa_ingresso,
                    "vrtaxaing": vrtaxaing,
                    "total_com_taxa": total_com_taxa,
                    "tipodesconto": "NENHUM",
                    "vrdesconto": 0,
                    "descontoativo": False,
                    "dsobsitcar": it.get("dsobsitcar") or it.get("obs"),
                    "nmparticipante": it.get("nmparticipante"),
                    "cpfparticipante": it.get("cpfparticipante"),
                }
            )

            continue

        produto_id_int = int(produto_id or 0)

        produto = (
            db.query(Produto)
            .filter(Produto.produto_id == produto_id_int)
            .first()
        )

        if not produto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produto {produto_id_int} não encontrado",
            )

        if (produto.sitproduto or "").upper() != "ATIVO":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produto '{produto.nmproduto}' não está disponível",
            )

        vrprecofinal, descontoativo = calcular_preco_final(produto)
        vrunitario = round(float(vrprecofinal), 2)
        subtotal = round(vrunitario * qt, 2)

        total += subtotal

        itens_recalculados.append(
            {
                "produto_id": produto.produto_id,
                "lote_id": None,
                "idtipoproduto": "P",
                "nmproduto": produto.nmproduto,
                "qt": qt,
                "qtitcarrinho": qt,
                "vrunitario": vrunitario,
                "subtotal": subtotal,
                "percentual_taxa_ingresso": 0,
                "vrtaxaing": 0,
                "total_com_taxa": subtotal,
                "tipodesconto": produto.tipodesconto or "NENHUM",
                "vrdesconto": float(produto.vrdesconto or 0),
                "descontoativo": descontoativo,
                "dsobsitcar": it.get("dsobsitcar") or it.get("obs"),
                "nmparticipante": it.get("nmparticipante"),
                "cpfparticipante": it.get("cpfparticipante"),
            }
        )

    return itens_recalculados, round(total, 2)


def _montar_itens_asaas(
    itens_recalculados: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    itens_asaas = []
    total_taxa_conveniencia = 0.0

    for item in itens_recalculados:
        nome = item.get("nmproduto") or "Item Clubbar"
        tipo = (item.get("idtipoproduto") or "P").upper()

        if tipo == "I":
            descricao_item = "Ingresso"
            referencia = f"LOTE-{item.get('lote_id') or 'SEM-ID'}"

            total_taxa_conveniencia += float(item.get("vrtaxaing") or 0)
        else:
            descricao_item = "Produto"
            referencia = f"PRODUTO-{item.get('produto_id') or 'SEM-ID'}"

        itens_asaas.append(
            {
                "externalReference": referencia,
                "name": nome[:100],
                "description": descricao_item,
                "quantity": int(item.get("qtitcarrinho") or item.get("qt") or 1),
                "value": round(float(item.get("vrunitario") or 0), 2),
            }
        )

    if total_taxa_conveniencia > 0:
        itens_asaas.append(
            {
                "externalReference": "TAXA-CONVENIENCIA",
                "name": "Taxa de conveniência",
                "description": "Taxa de serviço Clubbar",
                "quantity": 1,
                "value": round(total_taxa_conveniencia, 2),
            }
        )

    return itens_asaas


@router.post("/pagar-novo")
async def pagar_novo(payload: PagarNovoIn, db: Session = Depends(get_db)):
    metodo = (payload.dsmetodopag or "PIX").strip().upper()

    try:
        carrinho = get_carrinho(db, payload.cliente_id, payload.loja_id)

        if not carrinho:
            raise HTTPException(status_code=404, detail="Carrinho não encontrado")

        itens = carrinho.get("itens") or []

        if not isinstance(itens, list):
            raise HTTPException(
                status_code=500,
                detail="Formato inválido dos itens do carrinho",
            )

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
                        "qr_code_base64": transaction_data.get(
                            "qr_code_base64",
                            "",
                        ),
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

        itens_car = carrinho.get("itens") or []

        if not isinstance(itens_car, list):
            raise HTTPException(
                status_code=500,
                detail="Formato inválido dos itens do carrinho",
            )

        if not itens_car:
            raise HTTPException(status_code=400, detail="Carrinho vazio")

        itens_recalculados, total_recalculado = _recalcular_itens_carrinho(
            db,
            itens_car, payload.percentual_taxa_ingresso
        )

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

        try:
            await obter_ou_criar_customer_asaas(
                db,
                cliente_id=payload.cliente_id,
            )

            await sincronizar_cliente_com_asaas_se_precisar(
                db,
                cliente_id=payload.cliente_id,
            )
        except Exception as e:
            print("[ASAAS] Erro ao sincronizar customer:", repr(e))

        external_reference = f"CARRINHO-{carrinho_id}"
        valor_atual = round(float(total_recalculado or 0), 2)

        items_asaas = _montar_itens_asaas(itens_recalculados)

        pagamento = await criar_checkout_asaas(
            valor=total_recalculado,
            descricao=f"Compra Clubbar - Carrinho {carrinho_id}",
            external_reference=external_reference,
            carrinho_id=carrinho_id,
            nome_cliente=cliente.nmcliente,
            email_cliente=cliente.emailcliente,
            cpf_cliente=cliente.nrcpfcliente,
            celular_cliente=cliente.nrtelcliente,
            endcliente=cliente.endcliente,
            nrendcliente=cliente.nrendcliente,
            complcliente=cliente.complcliente,
            bairrocliente=cliente.bairrocliente,
            cepcliente=cliente.cepcliente,
            items=items_asaas,
        )

        checkout_id = pagamento.get("id")
        checkout_url = pagamento.get("link")
        status_checkout = pagamento.get("status") or "ACTIVE"

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
            status=status_checkout,
            valor=valor_atual,
        )

        db.add(novo)
        db.commit()

        return {
            "ok": True,
            "gateway": "ASAAS",
            "carrinho_id": carrinho_id,
            "pagamento_id": checkout_id,
            "status": status_checkout,
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