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
                detail=f"Produto {produto_id_int} não encontrado",
            )

        if (produto.sitproduto or "").upper() != "ATIVO":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Produto '{produto.nmproduto}' não está mais disponível. Retire do carrinho",
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
                    detail=f"Lote {lote_id_int} não encontrado",
                )

            vrunitario = round(float(lote.vrprecolote or 0), 2)
            subtotal   = round(vrunitario * qt_prod, 2)

            total_geral += it.get("vrtaxaitvenda")

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
                    "total_com_taxa" : subtotal+it.get("vrtaxaitvenda"),
                    "tipodesconto"   : "NENHUM",
                    "vrdesconto"     : 0,
                    "descontoativo"  : False,
                    "dsobsitcar"     : it.get("dsobsitcar"),
                    "nmparticipante" : it.get("nmparticipante"),
                    "cpfparticipante": it.get("cpfparticipante"),
                    "pctaxaitvenda"  : it.get("pctaxaitvenda"),
                    "vrtaxaitvenda"  : it.get("vrtaxaitvenda"),                
                }
            )

            continue

        vrprecofinal, descontoativo = calcular_preco_final(produto)
        vrunitario = round(float(vrprecofinal), 2)
        subtotal   = round(vrunitario * qt_prod, 2)

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
                "total_com_taxa" : subtotal+it.get("vrtaxaitvenda"),
                "tipodesconto"   : produto.tipodesconto or "NENHUM",
                "vrdesconto"     : float(produto.vrdesconto or 0),
                "descontoativo"  : descontoativo,
                "dsobsitcar"     : it.get("dsobsitcar") or it.get("obs"),
                "nmparticipante" : it.get("nmparticipante"),
                "cpfparticipante": it.get("cpfparticipante"),
                "pctaxaitvenda"  : it.get("pctaxaitvenda"),
                "vrtaxaitvenda"  : it.get("vrtaxaitvenda"),            
            }
        )

    return itens_recalculados, round(total_geral, 2)


def _montar_itens_asaas(
    itens_recalculados: list[Dict[str, Any]],
    percentual_taxa_ingresso: float = 0.0,
) -> tuple[list[Dict[str, Any]], float]:

    itens_asaas = []
    vr_taxa_ingresso = 0.0
    valor_total_com_taxa = 0.0

    percentual_taxa_ingresso = float(percentual_taxa_ingresso or 0)

    for item in itens_recalculados:
        nome = item.get("nmproduto") or "Item Clubbar"
        tipo = (item.get("idtipoproduto") or "P").upper()

        quantidade     = int(item.get("qtitcarrinho") or 1)
        valor_unitario = round(float(item.get("vrunitario") or 0), 2)
        subtotal_item  = round(valor_unitario * quantidade, 2)

        valor_total_com_taxa += subtotal_item

        if tipo == "I":
            descricao_item = "Ingresso"
            referencia = f"LOTE-{item.get('lote_id') or 'SEM-ID'}"

            taxa_item = round(
                subtotal_item * (percentual_taxa_ingresso / 100),
                2,
            )

            vr_taxa_ingresso += taxa_item
        else:
            descricao_item = "Produto"
            referencia = f"PRODUTO-{item.get('produto_id') or 'SEM-ID'}"

        itens_asaas.append(
            {
                "externalReference": referencia,
                "name": nome[:100],
                "description": descricao_item,
                "quantity": quantidade,
                "value": valor_unitario,
            }
        )

    vr_taxa_ingresso = round(vr_taxa_ingresso, 2)
    valor_total_com_taxa = round(valor_total_com_taxa + vr_taxa_ingresso, 2)


    if vr_taxa_ingresso > 0:
        itens_asaas.append(
            {
                "externalReference": "TAXA-CONVENIENCIA",
                "name": "Taxa de conveniência ingresso",
                "description": f"Taxa de serviço Clubbar (somente para ingressos) ({percentual_taxa_ingresso:.2f}%)",
                "quantity": 1,
                "value": vr_taxa_ingresso,
            }
        )

    return itens_asaas, valor_total_com_taxa


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
            itens_car
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

        items_asaas, valor_total_com_taxa = _montar_itens_asaas(
            itens_recalculados,
            percentual_taxa_ingresso=float(payload.percentual_taxa_ingresso or 0),
        )

        pagamento = await criar_checkout_asaas(
            valor=valor_total_com_taxa,
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
