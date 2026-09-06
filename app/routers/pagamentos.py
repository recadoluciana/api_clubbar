# app/routers/pagamentos.py
from __future__ import annotations

import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict
from contextlib import nullcontext
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.pagamentos import PagarNovoIn

from app.models.carrinho import Carrinho
from app.models.venda import Venda
from app.models.produto import Produto
from app.models.eventolote import EventoLote
from app.models.cashback_movimento import CashbackMovimento
from app.models.cliente import Cliente
from app.models.checkout_asaas import CheckoutAsaas
from app.models.checkout_asaas_item import CheckoutAsaasItem
from app.core.config import APP_ENV, ASAAS_API_KEY, ASAAS_PIX_ADDRESS_KEY, ASAAS_CLUBBAR_WALLET_ID

from app.services.carrinho_service import get_carrinho
from app.services.cliente_service import get_cliente

from app.routers.produtos import calcular_preco_final

from app.services.asaas_service import (
    obter_ou_criar_customer_asaas,
    criar_checkout_asaas,
    criar_referencia_checkout_asaas,
    buscar_pagamento_confirmado_por_checkout,
    buscar_pagamento_confirmado_por_qrcode_pix,
    buscar_pagamento_confirmado_por_referencia,
    atualizar_cliente_por_customer_asaas,
    criar_qrcode_pix_estatico_asaas,
    cancelar_checkout_asaas,
    excluir_qrcode_pix_estatico_asaas,
)
from app.services.repasse_service import criar_repasse_da_venda
from app.services.cashback_service import reservar_uso, vincular_uso_ao_checkout, cancelar_uso_pendente
from app.services.onboarding_parceiro_service import validar_publicacao_loja
from app.services.asaas_split_service import obter_conta_asaas_da_loja, montar_split_clubbar

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])


def _valor_cashback_gerado(db: Session, venda_id: int | None) -> float:
    if not venda_id:
        return 0.0
    movimento = (
        db.query(CashbackMovimento)
        .filter(
            CashbackMovimento.venda_origem_id == venda_id,
            CashbackMovimento.tipomovimento == "CREDITO",
            CashbackMovimento.sitcashback.in_(["PENDENTE", "DISPONIVEL"]),
        )
        .first()
    )
    return float(movimento.vrcashback or 0) if movimento else 0.0


async def _cancelar_tentativas_anteriores(
    db: Session,
    carrinho_id: int,
) -> None:
    tentativas = (
        db.query(CheckoutAsaas)
        .filter(
            CheckoutAsaas.carrinho_id == carrinho_id,
            CheckoutAsaas.venda_id.is_(None),
            CheckoutAsaas.status.notin_(['CANCELLED', 'CANCELED', 'EXPIRED']),
        )
        .order_by(CheckoutAsaas.checkout_asaas_id.desc())
        .all()
    )
    for tentativa in tentativas:
        api_key_tentativa = ASAAS_API_KEY
        if tentativa.asaas_wallet_loja:
            api_key_tentativa, _ = obter_conta_asaas_da_loja(db, tentativa.loja_id)
        if tentativa.pix_qr_code_id:
            await excluir_qrcode_pix_estatico_asaas(
                tentativa.pix_qr_code_id, api_key_tentativa
            )
        elif tentativa.checkout_id:
            await cancelar_checkout_asaas(tentativa.checkout_id, api_key_tentativa)
        tentativa.status = 'CANCELLED'
        cancelar_uso_pendente(db, tentativa)

    if tentativas:
        db.commit()


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
        if tipo_prod == "I" or it.get("lote_id"):
            raise HTTPException(
                status_code=409,
                detail="Carrinho aceita somente produtos. Compre ingressos pela reserva do evento.",
            )
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


def _salvar_snapshot_checkout(
    db: Session,
    checkout_asaas_id: int,
    itens: list[Dict[str, Any]],
) -> None:
    for item in itens:
        db.add(CheckoutAsaasItem(
            checkout_asaas_id=checkout_asaas_id,
            produto_id=int(item['produto_id']),
            lote_id=item.get('lote_id'),
            idtipoproduto=str(item.get('idtipoproduto') or 'P'),
            nmproduto=str(item.get('nmproduto') or 'Produto'),
            quantidade=int(item.get('qtitcarrinho') or item.get('qt_prod') or 1),
            vrunitario=float(item.get('vrunitario') or 0),
            subtotal=float(item.get('subtotal') or 0),
            total_com_taxa=float(item.get('total_com_taxa') or 0),
            pctaxaitvenda=float(item.get('pctaxaitvenda') or 0),
            vrtaxaitvenda=float(item.get('vrtaxaitvenda') or 0),
            dsobsitem=item.get('dsobsitcar'),
            nmparticipante=item.get('nmparticipante'),
            cpfparticipante=item.get('cpfparticipante'),
        ))


@router.post('/pix')
async def criar_pix_cliente(payload: PagarNovoIn, db: Session = Depends(get_db)):
    try:
        if not ASAAS_API_KEY or not ASAAS_PIX_ADDRESS_KEY:
            raise HTTPException(status_code=503, detail='PIX Asaas nao configurado')
        carrinho = get_carrinho(
            db, payload.cliente_id, payload.loja_id, payload.usuario_id
        )
        if not carrinho:
            raise HTTPException(status_code=404, detail='Carrinho nao encontrado')
        itens = carrinho.get('itens') or []
        if not itens:
            raise HTTPException(status_code=400, detail='Carrinho vazio')
        carrinho_id = int(carrinho.get('carrinho_id') or 0)
        if not carrinho_id:
            raise HTTPException(status_code=400, detail='Carrinho invalido')

        agora = datetime.now()
        await _cancelar_tentativas_anteriores(db, carrinho_id)
        itens_recalculados, _ = _recalcular_itens_carrinho(db, itens)
        _, valor_total, valor_taxa = _montar_itens_asaas(itens_recalculados)
        valor_taxa = round(sum(float(item.get("vrtaxaitvenda") or 0) * int(item.get("qtitcarrinho") or 1) for item in itens_recalculados), 2)
        valor_cashback, debitos_cashback = reservar_uso(db, cliente_id=payload.cliente_id, organizacao_id=payload.organizacao_id, loja_id=payload.loja_id, total_produtos=valor_total, valor_solicitado=payload.valor_cashback) if payload.usar_cashback else (Decimal("0"), [])
        valor_cobrado = round(float(Decimal(str(valor_total)) - valor_cashback), 2)
        valor_taxa = round(valor_taxa * (valor_cobrado / valor_total), 2) if valor_total else 0
        external_reference = (
            f'PIX-{APP_ENV.upper()}-CLIENT-{carrinho_id}-{uuid.uuid4().hex[:12]}'
        )
        qr = await criar_qrcode_pix_estatico_asaas(
            address_key=ASAAS_PIX_ADDRESS_KEY,
            valor=valor_cobrado,
            descricao=f'Clubbar carrinho {carrinho_id}',
            api_key=ASAAS_API_KEY,
            external_reference=external_reference,
            expiracao_segundos=300,
        )
        pix_id = str(qr['id'])
        registro = CheckoutAsaas(
            carrinho_id=carrinho_id,
            cliente_id=payload.cliente_id,
            loja_id=payload.loja_id,
            venda_id=None,
            checkout_id=pix_id,
            pix_qr_code_id=pix_id,
            pix_payload=str(qr['payload']),
            pix_encoded_image=str(qr.get('encodedImage') or ''),
            pix_expiration_date=agora + timedelta(minutes=5),
            external_reference=external_reference,
            status='PENDING',
            valor=valor_cobrado,
            vrtaxaclubbar=valor_taxa,
            vrcashbackusado=valor_cashback,
        )
        db.add(registro)
        db.flush()
        vincular_uso_ao_checkout(db, debitos_cashback, registro)
        db.commit()
        return {
            'venda_id': None,
            'pagamento_id': pix_id,
            'pix_qr_code_id': pix_id,
            'pix_copia_cola': qr['payload'],
            'encoded_image': qr.get('encodedImage'),
            'expiration_date': qr.get('expirationDate'),
            'valor_total': valor_cobrado,
            'valor_original': valor_total,
            'cashback_utilizado': float(valor_cashback),
            'status': 'PENDENTE',
            'reutilizado': False,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print('[ASAAS PIX CLIENT][ERRO]', repr(exc))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f'Erro ao gerar PIX Asaas ({type(exc).__name__}): {exc}',
        )


@router.post("/pagar-asaas")
async def pagar_asaas(
    payload: PagarNovoIn,
    db: Session = Depends(get_db),
):
    try:
        validar_publicacao_loja(db, payload.loja_id)

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

        await _cancelar_tentativas_anteriores(db, carrinho_id)

        cliente = (
            db.query(Cliente)
            .filter(Cliente.cliente_id == payload.cliente_id)
            .first()
        )

        if not cliente:
            raise HTTPException(status_code=404, detail="Cliente nÃ£o encontrado")

        api_key_loja, wallet_loja = obter_conta_asaas_da_loja(db, payload.loja_id)
        external_reference = criar_referencia_checkout_asaas(carrinho_id)
        items_asaas, valor_total_com_taxa, valor_taxa_clubbar = _montar_itens_asaas(
            itens_recalculados
        )
        valor_cashback, debitos_cashback = reservar_uso(db, cliente_id=payload.cliente_id, organizacao_id=payload.organizacao_id, loja_id=payload.loja_id, total_produtos=valor_total_com_taxa, valor_solicitado=payload.valor_cashback) if payload.usar_cashback else (Decimal("0"), [])
        valor_cobrado = round(float(Decimal(str(valor_total_com_taxa)) - valor_cashback), 2)
        taxa_produtos = round(sum(float(item.get("vrtaxaitvenda") or 0) * int(item.get("qtitcarrinho") or 1) for item in itens_recalculados), 2)
        valor_taxa_clubbar = round(taxa_produtos * (valor_cobrado / valor_total_com_taxa), 2) if valor_total_com_taxa else 0
        if valor_cashback > 0:
            items_asaas = [{"externalReference": f"CARRINHO-{carrinho_id}", "name": "Compra Clubbar", "description": "Produtos com desconto de cashback", "quantity": 1, "value": valor_cobrado}]

        pagamento = await criar_checkout_asaas(
            valor=valor_cobrado,
            descricao=f"Compra Clubbar - Carrinho {carrinho_id}",
            external_reference=external_reference,
            carrinho_id=carrinho_id,
            api_key=api_key_loja,
            splits=montar_split_clubbar(valor_taxa_clubbar),
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
            valor=valor_cobrado,
            vrtaxaclubbar=valor_taxa_clubbar,
            vrcashbackusado=valor_cashback,
            asaas_wallet_loja=wallet_loja,
            asaas_wallet_clubbar=ASAAS_CLUBBAR_WALLET_ID,
        )

        db.add(novo)
        db.flush()
        vincular_uso_ao_checkout(db, debitos_cashback, novo)
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
            "valor_original": valor_total_com_taxa,
            "valor_cobrado": valor_cobrado,
            "cashback_utilizado": float(valor_cashback),
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
    checkout_consultado = (
        db.query(CheckoutAsaas)
        .filter(CheckoutAsaas.checkout_id == checkout_id)
        .first()
    )
    if (
        checkout_consultado
        and getattr(checkout_consultado, 'carrinho_id', None) is not None
        and not getattr(checkout_consultado, 'venda_id', None)
    ):
        tentativa_atual = (
            db.query(CheckoutAsaas)
            .filter(
                CheckoutAsaas.carrinho_id == checkout_consultado.carrinho_id,
                CheckoutAsaas.venda_id.is_(None),
            )
            .order_by(CheckoutAsaas.checkout_asaas_id.desc())
            .first()
        )
        if (
            (checkout_consultado.status or '').upper()
            in {'CANCELLED', 'CANCELED', 'EXPIRED'}
            or tentativa_atual is None
            or tentativa_atual.checkout_asaas_id
            != checkout_consultado.checkout_asaas_id
        ):
            return {
                'pagamento_id': checkout_consultado.checkout_id,
                'status': 'SUBSTITUIDO',
                'detail': 'Esta tentativa foi substituida por uma mais recente.',
            }
    checkout = checkout_consultado
    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout Asaas nao encontrado")
    api_key_checkout = ASAAS_API_KEY
    if getattr(checkout, "asaas_wallet_loja", None):
        api_key_checkout, _ = obter_conta_asaas_da_loja(db, checkout.loja_id)
    status_atual = (checkout.status or "PENDENTE").upper()
    if (
        status_atual not in {"PAID", "RECEIVED", "CONFIRMED"}
        and api_key_checkout
        and getattr(checkout, "checkout_asaas_id", None)
    ):
        if getattr(checkout, "pix_qr_code_id", None):
            pagamento = await buscar_pagamento_confirmado_por_qrcode_pix(
                checkout.pix_qr_code_id, api_key_checkout
            )
        else:
            pagamento = await buscar_pagamento_confirmado_por_checkout(
                checkout.checkout_id, api_key_checkout
            )
            if not pagamento:
                pagamento = await buscar_pagamento_confirmado_por_referencia(
                    getattr(checkout, "external_reference", ""), api_key_checkout
                )
        if pagamento:
            from app.services.venda_gateway_service import (
                criar_venda_paga_por_carrinho_gateway,
                criar_venda_paga_por_checkout_snapshot,
                validar_confirmacao_asaas_checkout,
            )

            checkout_bloqueado = (
                db.query(CheckoutAsaas)
                .filter(CheckoutAsaas.checkout_asaas_id == checkout.checkout_asaas_id)
                .with_for_update()
                .first()
            )
            if not checkout_bloqueado:
                raise HTTPException(404, 'Checkout Asaas nao encontrado')
            checkout = checkout_bloqueado
            if checkout.venda_id:
                db.commit()
                return {
                    'pagamento_id': checkout.checkout_id,
                    'status': 'PAGO',
                    'venda_id': checkout.venda_id,
                    'cashback_gerado': _valor_cashback_gerado(
                        db, checkout.venda_id
                    ),
                }

            validar_confirmacao_asaas_checkout(
                db,
                checkout=checkout,
                pagamento=pagamento,
                origem_confirmacao='CONSULTA',
            )
            possui_snapshot = (
                db.query(CheckoutAsaasItem)
                .filter(
                    CheckoutAsaasItem.checkout_asaas_id
                    == checkout.checkout_asaas_id
                )
                .first()
                is not None
            )
            possui_snapshot = False
            if possui_snapshot:
                await criar_venda_paga_por_checkout_snapshot(
                    db,
                    checkout_asaas_id=checkout.checkout_asaas_id,
                    origem_confirmacao='CONSULTA',
                    gateway="ASAAS",
                    pagamento=pagamento,
                )
            else:
                resultado_venda = await criar_venda_paga_por_carrinho_gateway(
                    db,
                    carrinho_id=checkout.carrinho_id,
                    gateway="ASAAS",
                    pagamento=pagamento,
                )
                checkout.venda_id = resultado_venda.get('venda_id')
            checkout.status = "PAID"
            checkout.payment_id = str(pagamento.get("id") or "") or None
            db.commit()
            if (
                str(pagamento.get("billingType") or "").upper()
                in {"CREDIT_CARD", "DEBIT_CARD"}
                and pagamento.get("customer")
                and checkout.cliente_id
            ):
                try:
                    await atualizar_cliente_por_customer_asaas(
                        db,
                        cliente_id=checkout.cliente_id,
                        customer_id=str(pagamento["customer"]),
                        api_key=api_key_checkout,
                    )
                except Exception as exc:
                    # O pagamento e a venda permanecem válidos mesmo se a
                    # atualização complementar do perfil falhar.
                    print("[ASAAS] Erro ao atualizar endereco do cliente:", repr(exc))
            status_atual = "PAID"
    pago = status_atual in {"PAID", "RECEIVED", "CONFIRMED"}
    return {
        "pagamento_id": checkout.checkout_id,
        "status": "PAGO" if pago else status_atual,
        "venda_id": checkout.venda_id if pago else None,
        "cashback_gerado": _valor_cashback_gerado(db, checkout.venda_id)
        if pago
        else 0.0,
    }
