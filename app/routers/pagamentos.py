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
from app.core.config import ASAAS_API_KEY

from app.services.carrinho_service import get_carrinho
from app.services.cliente_service import get_cliente

from app.routers.produtos import calcular_preco_final

from app.services.asaas_service import (
    obter_ou_criar_customer_asaas,
    criar_checkout_asaas,
    criar_referencia_checkout_asaas,
    buscar_pagamento_confirmado_por_qrcode_pix,
    buscar_pagamento_confirmado_por_referencia,
)
from app.services.repasse_service import criar_repasse_da_venda

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])


def db_tx(db: Session):
    return nullcontext() if db.in_transaction() else db.begin()


def _recalcular_itens_carrinho(
    db: Session,
    itens: list[Dict[str, Any]],
) -> tuple[list[Dict[str, Any]], float]:
    itens_recalculados = []
    total_geral = 0.0


    for it in itens:
        tipo_prod  = (it.get("idtipoproduto") or "P").upper()
        qt_prod    = (it.get("qtitcarrinho") or 1)
        produto_id = it.get("produto_id")
        lote_id    = it.get("lote_id")

        # >>>> verifica o produto no banco >>>>>>>>>>>>>>>>> #
        produto_id_int = int(produto_id or 0)
        produto = (
            db.query(Produto)
            .filter(Produto.produto_id == produto_id_int)
            .first()
        )

        if not produto:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produto {produto_id_int} nÃ£o encontrado",
            )

        if (produto.sitproduto or "").upper() != "ATIVO":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produto '{produto.nmproduto}' nÃ£o estÃ¡ mais disponÃ­vel. Retire do carrinho",
            )


        if tipo_prod == "I":
            lote_id_int = int(lote_id or 0)

            lote = (
                db.query(EventoLote)
                .filter(EventoLote.lote_id == lote_id_int)
                .first()
            )

            if not lote:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Lote {lote_id_int} nÃ£o encontrado",
                )

            vrunitario = round(float(lote.vrprecolote or 0), 2)
            subtotal   = round(vrunitario * qt_prod, 2)

            percentual_taxa = round(float(it.get("pctaxaitvenda") or 0), 2)
            taxa_unitaria = round(vrunitario * percentual_taxa / 100, 2)
            taxa_linha = round(taxa_unitaria * qt_prod, 2)
            total_geral += subtotal + taxa_linha

            itens_recalculados.append(
                {
                    "produto_id"     : produto.produto_id,
                    "lote_id"        : lote.lote_id,
                    "idtipoproduto"  : "I",
                    "nmproduto"      : produto.nmproduto,
                    "qt_prod"        : qt_prod,
                    "qtitcarrinho"   : qt_prod,
                    "vrunitario"     : vrunitario,
                    "subtotal"       : subtotal,
                    "total_com_taxa" : round(subtotal + taxa_linha, 2),
                    "tipodesconto"   : "NENHUM",
                    "vrdesconto"     : 0,
                    "descontoativo"  : False,
                    "dsobsitcar"     : it.get("dsobsitcar"),
                    "nmparticipante" : it.get("nmparticipante"),
                    "cpfparticipante": it.get("cpfparticipante"),
                    "pctaxaitvenda"  : it.get("pctaxaitvenda"),
                    "vrtaxaitvenda"  : taxa_unitaria,
                }
            )

            continue

        vrprecofinal, descontoativo = calcular_preco_final(produto)
        vrunitario = round(float(vrprecofinal), 2)
        subtotal   = round(vrunitario * qt_prod, 2)

        percentual_taxa = round(float(it.get("pctaxaitvenda") or 0), 2)
        taxa_unitaria = round(vrunitario * percentual_taxa / 100, 2)
        taxa_linha = round(taxa_unitaria * qt_prod, 2)
        total_geral += subtotal

        itens_recalculados.append(
            {
                "produto_id"     : produto.produto_id,
                "lote_id"        : None,
                "idtipoproduto"  : produto.idtipoproduto,
                "nmproduto"      : produto.nmproduto,
                "qt_prod"        : qt_prod,
                "qtitcarrinho"   : qt_prod,
                "vrunitario"     : vrunitario,
                "subtotal"       : subtotal,
                "total_com_taxa" : subtotal,
                "tipodesconto"   : produto.tipodesconto or "NENHUM",
                "vrdesconto"     : float(produto.vrdesconto or 0),
                "descontoativo"  : descontoativo,
                "dsobsitcar"     : it.get("dsobsitcar") or it.get("obs"),
                "nmparticipante" : it.get("nmparticipante"),
                "cpfparticipante": it.get("cpfparticipante"),
                "pctaxaitvenda"  : it.get("pctaxaitvenda"),
                "vrtaxaitvenda"  : taxa_unitaria,
            }
        )

    return itens_recalculados, round(total_geral, 2)


def _montar_itens_asaas(
    itens_recalculados: list[Dict[str, Any]],
) -> tuple[list[Dict[str, Any]], float, float]:

    itens_asaas = []
    vr_taxa_clubbar = 0.0
    valor_total_com_taxa = 0.0

    for item in itens_recalculados:
        nome = item.get("nmproduto") or "Item Clubbar"
        tipo = (item.get("idtipoproduto") or "P").upper()

        quantidade     = int(item.get("qtitcarrinho") or 1)
        valor_unitario = round(float(item.get("vrunitario") or 0), 2)
        subtotal_item  = round(valor_unitario * quantidade, 2)

        valor_total_com_taxa += subtotal_item

        if tipo == "I":
            descricao_item = f"Ingresso LOTE-{item.get('lote_id') or 'SEM-ID'}"
            referencia = f"LOTE-{item.get('lote_id') or 'SEM-ID'}"
        else:
            descricao_item = "Produto"
            referencia = f"PRODUTO-{item.get('produto_id') or 'SEM-ID'}"

        if tipo == "I":
            taxa_linha = round(float(item.get("vrtaxaitvenda") or 0), 2)
            valor_total_com_taxa += taxa_linha
            vr_taxa_clubbar += taxa_linha

        itens_asaas.append(
            {
                "externalReference": referencia,
                "name": nome[:30],
                "description": descricao_item,
                "quantity": quantidade,
                "value": valor_unitario,
            }
        )

    vr_taxa_clubbar = round(vr_taxa_clubbar, 2)
    valor_total_com_taxa = round(valor_total_com_taxa, 2)


    if any((item.get("idtipoproduto") or "P").upper() == "I" and float(item.get("vrtaxaitvenda") or 0) > 0 for item in itens_recalculados):
        itens_asaas.append(
            {
                "externalReference": "TAXA-CONVENIENCIA",
                "name": "Taxa de servi\u00e7o Clubbar",
                "description": "Taxa de servi\u00e7o Clubbar",
                "quantity": 1,
                "value": vr_taxa_clubbar,
            }
        )

    return itens_asaas, valor_total_com_taxa, vr_taxa_clubbar


@router.post("/pagar-asaas")
async def pagar_asaas(
    payload: PagarNovoIn,
    db: Session = Depends(get_db),
):
    try:
        carrinho = get_carrinho(
            db,
            payload.cliente_id,
            payload.loja_id,
            payload.usuario_id,
        )

        if not carrinho:
            raise HTTPException(status_code=404, detail="Carrinho nÃ£o encontrado")

        itens_car = carrinho.get("itens") or []

        if not isinstance(itens_car, list):
            raise HTTPException(
                status_code=500,
                detail="Formato invÃ¡lido dos itens do carrinho",
            )

        if not itens_car:
            raise HTTPException(status_code=400, detail="Carrinho vazio")

        itens_recalculados, total_recalculado = _recalcular_itens_carrinho(
            db,
            itens_car
        )

        carrinho_id = int(carrinho.get("carrinho_id") or 0)

        if carrinho_id == 0:
            raise HTTPException(status_code=400, detail="Carrinho invÃ¡lido")

        cliente = (
            db.query(Cliente)
            .filter(Cliente.cliente_id == payload.cliente_id)
            .first()
        )

        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente nÃ£o encontrado")

        if not ASAAS_API_KEY:
            raise HTTPException(status_code=503, detail="Conta global Asaas nÃ£o configurada")

        if cliente.cliente_padrao != "S":
            try:
                await obter_ou_criar_customer_asaas(
                    db,
                    cliente_id=payload.cliente_id,
                    api_key=ASAAS_API_KEY,
                )
            except Exception as e:
                print("[ASAAS] Erro ao sincronizar customer:", repr(e))
                raise
        external_reference = criar_referencia_checkout_asaas(carrinho_id)
        items_asaas, valor_total_com_taxa, valor_taxa_clubbar = _montar_itens_asaas(
            itens_recalculados
        )

        pagamento = await criar_checkout_asaas(
            valor=valor_total_com_taxa,
            descricao=f"Compra Clubbar - Carrinho {carrinho_id}",
            external_reference=external_reference,
            carrinho_id=carrinho_id,
            api_key=ASAAS_API_KEY,
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
            billing_types=(
                ["PIX"]
                if payload.dsmetodopag == "PIX"
                else ["CREDIT_CARD"]
                if payload.dsmetodopag in {"CREDIT_CARD", "CREDITO"}
                else ["PIX", "CREDIT_CARD"]
            ),
            origem_checkout=payload.origem_checkout,
        )

        checkout_id = pagamento.get("id")
        checkout_url = pagamento.get("link")
        status_checkout = pagamento.get("status") or "ACTIVE"

        if not checkout_id or not checkout_url:
            raise HTTPException(
                status_code=500,
                detail={
                    "erro": "Asaas nÃ£o retornou id ou link do checkout.",
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
            valor=valor_total_com_taxa,
            vrtaxaclubbar=valor_taxa_clubbar,
            asaas_wallet_loja=None,
            asaas_wallet_clubbar=None,
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
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        print("[ASAAS][ERRO]", repr(e))
        print(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail=f"Erro ao gerar pagamento Asaas ({type(e).__name__}): {e}",
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


@router.get("/asaas/status/{checkout_id}")
async def status_checkout_asaas(checkout_id: str, db: Session = Depends(get_db)):
    checkout = db.query(CheckoutAsaas).filter(CheckoutAsaas.checkout_id == checkout_id).first()
    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout Asaas nao encontrado")
    status_atual = (checkout.status or "PENDENTE").upper()
    if (
        status_atual not in {"PAID", "RECEIVED", "CONFIRMED"}
        and ASAAS_API_KEY
        and getattr(checkout, "checkout_asaas_id", None)
    ):
        if getattr(checkout, "pix_qr_code_id", None):
            pagamento = await buscar_pagamento_confirmado_por_qrcode_pix(
                checkout.pix_qr_code_id, ASAAS_API_KEY
            )
        else:
            pagamento = await buscar_pagamento_confirmado_por_referencia(
                getattr(checkout, "external_reference", ""), ASAAS_API_KEY
            )
        if pagamento:
            from app.services.venda_gateway_service import (
                criar_venda_paga_por_checkout_snapshot,
            )

            await criar_venda_paga_por_checkout_snapshot(
                db,
                checkout_asaas_id=checkout.checkout_asaas_id,
                gateway="ASAAS",
                pagamento=pagamento,
            )
            checkout.status = "PAID"
            checkout.payment_id = str(pagamento.get("id") or "") or None
            db.commit()
            status_atual = "PAID"
    return {"pagamento_id": checkout.checkout_id, "status": "PAGO" if status_atual in {"PAID", "RECEIVED", "CONFIRMED"} else status_atual}
