# app/routers/pagamentos.py
from __future__ import annotations

import json
import traceback
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict
from contextlib import nullcontext
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_usuario_logado
from app.core.cliente_auth import exigir_cliente_autenticado
from app.schemas.pagamentos import (
    CriarPedidoEntregaIn,
    PagarNovoIn,
    ResgatarCortesiaProdutoIn,
)

from app.models.carrinho import Carrinho
from app.models.itcarrinho import ItCarrinho
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda
from app.models.pedidoentrega import PedidoEntrega
from app.models.venda import Venda
from app.models.produto import Produto
from app.models.loja import Loja
from app.models.cardapio import Cardapio, CardapioItem, CardapioVersao
from app.models.eventolote import EventoLote
from app.models.eventolotepreco import EventoLotePreco
from app.models.cashback_movimento import CashbackMovimento
from app.models.cliente import Cliente
from app.models.checkout_asaas import CheckoutAsaas
from app.models.checkout_asaas_item import CheckoutAsaasItem
from app.core.config import APP_ENV, ASAAS_API_KEY, ASAAS_CLUBBAR_WALLET_ID

from app.services.carrinho_service import get_carrinho
from app.services.cliente_service import get_cliente
from app.services.localidade_entrega_service import resolver_localidade_entrega
from app.services.venda_service import criar_ou_obter_venda_idempotente, gerar_token_qr
from app.services.pagamento_status_service import set_venda_como_paga
from app.services.notificacao_produtos_service import enviar_produtos_confirmados_da_venda

from app.routers.produtos import calcular_preco_final, _itens_cardapio_em_exibicao
from app.services.cortesia_produto_service import (
    validar_cliente_sem_cortesia_pendente,
    validar_cortesia_disponivel,
)
from app.utils.datetime_utils import FUSO_BRASIL

from app.services.asaas_service import (
    obter_ou_criar_customer_asaas,
    criar_checkout_asaas,
    criar_referencia_checkout_asaas,
    buscar_pagamento_confirmado_por_checkout,
    buscar_pagamento_confirmado_por_qrcode_pix,
    buscar_pagamento_confirmado_por_referencia,
    atualizar_cliente_por_customer_asaas,
    criar_cobranca_pix_asaas,
    obter_ou_criar_customer_asaas_loja,
    buscar_pagamento_confirmado_por_id,
    confirmar_pagamento_sandbox_asaas,
    cancelar_pagamento_asaas,
    cancelar_checkout_asaas,
    excluir_qrcode_pix_estatico_asaas,
    validar_endereco_cobranca_para_cartao,
)
from app.services.cashback_service import reservar_uso, vincular_uso_ao_checkout, cancelar_uso_pendente
from app.services.onboarding_parceiro_service import validar_publicacao_loja
from app.services.asaas_split_service import obter_conta_asaas_da_loja, montar_splits_pagamento
from app.services.asaas_webhook_service import garantir_webhook_pagamentos_asaas
from app.services.campanha_doacao_service import (
    obter_campanha_doacao_vigente,
    registrar_snapshot_doacao,
    validar_campanha_para_split,
)
from app.utils.datetime_utils import iso_utc

router = APIRouter(prefix="/pagamentos", tags=["Pagamentos"])


def _exigir_valor_positivo(valor: float) -> None:
    if Decimal(str(valor)) <= 0:
        raise HTTPException(422, "O valor do pagamento deve ser maior que zero.")


def _enviar_confirmacao_produtos_sem_bloquear(db: Session, venda_id: int) -> None:
    """O e-mail é complementar: uma falha nele não altera a venda já paga."""
    try:
        enviar_produtos_confirmados_da_venda(db, venda_id)
    except Exception as exc:
        print("[PRODUTO] Não foi possível enviar e-mail:", repr(exc))


@router.post('/resgatar-cortesia-produto')
async def resgatar_cortesia_produto_direta(
    payload: ResgatarCortesiaProdutoIn,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Resgata uma cortesia diretamente na carteira, sem exibir o carrinho ao cliente."""
    exigir_cliente_autenticado(usuario, payload.cliente_id)

    try:
        validar_publicacao_loja(db, payload.loja_id)
        loja = (
            db.query(Loja)
            .filter(
                Loja.loja_id == payload.loja_id,
                Loja.organizacao_id == payload.organizacao_id,
            )
            .first()
        )
        if not loja:
            raise HTTPException(status_code=404, detail='Estabelecimento não encontrado.')

        # O bloqueio da conta do cliente serializa resgates simultâneos e
        # garante a regra de uma cortesia pendente por vez.
        cliente = (
            db.query(Cliente)
            .filter(Cliente.cliente_id == payload.cliente_id)
            .with_for_update()
            .first()
        )
        if not cliente:
            raise HTTPException(status_code=404, detail='Cliente não encontrado.')
        validar_cliente_sem_cortesia_pendente(
            db,
            cliente_id=payload.cliente_id,
        )

        agora = datetime.now(FUSO_BRASIL).replace(tzinfo=None)
        itens_visiveis = _itens_cardapio_em_exibicao(db, payload.loja_id, agora)
        item_visivel = None
        for candidato in itens_visiveis.values():
            if int(candidato.cardapioitem_id) == payload.cardapioitem_id:
                item_visivel = candidato
                break
        if not item_visivel:
            raise HTTPException(status_code=404, detail='Produto não está disponível neste cardápio.')

        item = (
            db.query(CardapioItem)
            .filter(CardapioItem.cardapioitem_id == payload.cardapioitem_id)
            .with_for_update()
            .first()
        )
        produto = (
            db.query(Produto)
            .filter(
                Produto.produto_id == item.produto_id,
                Produto.organizacao_id == payload.organizacao_id,
                Produto.sitproduto == 'ATIVO',
            )
            .first()
            if item
            else None
        )
        if not item or not produto:
            raise HTTPException(status_code=404, detail='Produto não encontrado.')

        preco_final, _ = calcular_preco_final(
            item.vrpreco,
            tipodesconto=item.tipodesconto,
            vrdesconto=item.vrdesconto,
            dtinidesconto=item.dtinidesconto,
            dtfimdesconto=item.dtfimdesconto,
        )
        if Decimal(str(preco_final)) > 0:
            raise HTTPException(status_code=409, detail='Este produto não é uma cortesia disponível.')

        validar_cortesia_disponivel(
            db,
            cardapioitem_id=payload.cardapioitem_id,
            quantidade=1,
            bloquear_item=True,
        )

        # Toda venda de produto precisa estar vinculada a um carrinho no banco.
        # Criamos um carrinho técnico, já fechado na confirmação, para que o
        # resgate direto não apareça no carrinho aberto do cliente nem viole a
        # regra de integridade ``chk_venda_origem`` da tabela de vendas.
        carrinho_resgate = Carrinho(
            organizacao_id=payload.organizacao_id,
            loja_id=payload.loja_id,
            cliente_id=payload.cliente_id,
            sitcarrinho='ABERTO',
        )
        db.add(carrinho_resgate)
        db.flush()

        venda = Venda(
            loja_id=payload.loja_id,
            organizacao_id=payload.organizacao_id,
            cliente_id=payload.cliente_id,
            carrinho_id=int(carrinho_resgate.carrinho_id),
            tipovenda='PRODUTO',
            dsplataforma='OUTROS',
            sitvenda='PENDENTE',
            totalvenda=0,
        )
        db.add(venda)
        db.flush()

        item_venda = ItVenda(
            venda_id=venda.venda_id,
            tipoitem='PRODUTO',
            produto_id=produto.produto_id,
            cardapioitem_id=item.cardapioitem_id,
            qtitvenda=1,
            vrunititvenda=0,
            identregaitvenda='NAO',
            qrtokenitvenda=gerar_token_qr(),
        )
        db.add(item_venda)
        db.flush()

        pagamento = PagVenda(
            venda_id=venda.venda_id,
            dsmetodopag='CORTESIA',
            vrpagvenda=0,
            sitpagvenda='PENDENTE',
            reference_id=f'CORTESIA-{venda.venda_id}',
            provedor='CORTESIA',
        )
        db.add(pagamento)
        db.flush()

        resultado_pagamento = set_venda_como_paga(
            db,
            venda_id=int(venda.venda_id),
            gateway='CORTESIA',
            payload={'id': f'CORTESIA-{venda.venda_id}', 'status': 'PAID'},
            finalizar_carrinho=True,
        )
        db.commit()
        if not resultado_pagamento.get('already_processed'):
            _enviar_confirmacao_produtos_sem_bloquear(db, int(venda.venda_id))
        return {
            'ok': True,
            'venda_id': int(venda.venda_id),
            'itvenda_id': int(item_venda.itvenda_id),
            'status': 'PAGA',
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print('[CORTESIA_DIRETA][ERRO]', repr(exc))
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail='Não foi possível resgatar a cortesia.')


@router.post('/resgatar-cortesia')
async def resgatar_cortesia_cliente(
    payload: PagarNovoIn,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Conclui um carrinho integralmente gratuito sem abrir o gateway."""
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    if payload.usuario_id is not None or payload.origem_checkout != 'CLIENT':
        raise HTTPException(status_code=403, detail='Origem de pagamento inválida')

    try:
        validar_publicacao_loja(db, payload.loja_id)
        carrinho = get_carrinho(
            db,
            payload.cliente_id,
            payload.loja_id,
            payload.usuario_id,
        )
        if not carrinho or not carrinho.get('itens'):
            raise HTTPException(status_code=400, detail='Carrinho vazio')

        carrinho_id = int(carrinho.get('carrinho_id') or 0)
        if not carrinho_id:
            raise HTTPException(status_code=400, detail='Carrinho inválido')

        itens_recalculados, total_recalculado = _recalcular_itens_carrinho(
            db,
            carrinho['itens'],
            payload.loja_id,
            payload.organizacao_id,
        )
        if not itens_recalculados:
            raise HTTPException(status_code=400, detail='Carrinho vazio')
        if Decimal(str(total_recalculado)) > 0:
            raise HTTPException(
                status_code=422,
                detail='Este carrinho possui itens pagos e deve seguir para o pagamento.',
            )

        await _cancelar_tentativas_anteriores(db, carrinho_id)

        carrinho_para_venda = dict(carrinho)
        carrinho_para_venda['itens'] = itens_recalculados
        carrinho_para_venda['total'] = 0
        venda_criada = await criar_ou_obter_venda_idempotente(
            db,
            cliente_id=payload.cliente_id,
            loja_id=payload.loja_id,
            organizacao_id=payload.organizacao_id,
            carrinho=carrinho_para_venda,
            plataforma='WEB',
            metodo_pagamento='OUTRO',
        )
        venda_id = int(venda_criada['venda_id'])
        pagamento = (
            db.query(PagVenda)
            .filter(PagVenda.venda_id == venda_id)
            .order_by(PagVenda.pagvenda_id.desc())
            .first()
        )
        if not pagamento:
            raise HTTPException(status_code=500, detail='Não foi possível concluir a cortesia.')
        pagamento.dsmetodopag = 'CORTESIA'
        pagamento.vrpagvenda = 0

        resultado_pagamento = set_venda_como_paga(
            db,
            venda_id=venda_id,
            gateway='CORTESIA',
            payload={'id': f'CORTESIA-{venda_id}', 'status': 'PAID'},
        )
        db.commit()
        if not resultado_pagamento.get('already_processed'):
            _enviar_confirmacao_produtos_sem_bloquear(db, venda_id)
        return {
            'ok': True,
            'venda_id': venda_id,
            'status': 'PAGA',
            'total': 0,
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print('[CORTESIA][ERRO]', repr(exc))
        print(traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail='Não foi possível resgatar a cortesia.',
        )


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
        if tentativa.payment_id:
            await cancelar_pagamento_asaas(tentativa.payment_id, api_key_tentativa)
        elif tentativa.pix_qr_code_id:
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
    loja_id: int,
    organizacao_id: int,
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

            preco = db.query(EventoLotePreco).filter(EventoLotePreco.lote_id == lote.lote_id, EventoLotePreco.tipopreco == "INTEIRA").first()
            vrunitario = round(float(preco.vrpreco if preco else 0), 2)
            subtotal   = round(vrunitario * qt_prod, 2)

            percentual_taxa = round(float(it.get("pctaxaitvenda") or 0), 2)
            # A taxa já foi calculada e congelada no carrinho, inclusive o piso por ingresso.
            taxa_unitaria = round(float(it.get("vrtaxaitvenda") or 0) / qt_prod, 2)
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

        if produto.organizacao_id != organizacao_id:
            raise HTTPException(
                status_code=409,
                detail=f"O produto '{produto.nmproduto}' não pertence a esta organização.",
            )
        vrunitario = round(float(it.get("vrprecoprod") or 0), 2)
        descontoativo = False
        subtotal   = round(vrunitario * qt_prod, 2)

        percentual_taxa = round(float(it.get("pctaxaitvenda") or 0), 2)
        taxa_unitaria = round(vrunitario * percentual_taxa / 100, 2)
        taxa_linha = round(taxa_unitaria * qt_prod, 2)
        total_geral += subtotal

        itens_recalculados.append(
            {
                "produto_id"     : produto.produto_id,
                "cardapioitem_id": it.get("cardapioitem_id"),
                "beneficio_resgate_id": it.get("beneficio_resgate_id"),
                "lote_id"        : None,
                "idtipoproduto"  : "P",
                "nmproduto"      : produto.nmproduto,
                "qt_prod"        : qt_prod,
                "qtitcarrinho"   : qt_prod,
                "vrunitario"     : vrunitario,
                "subtotal"       : subtotal,
                "total_com_taxa" : subtotal,
                "tipodesconto"   : "NENHUM",
                "vrdesconto"     : 0,
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
            cardapioitem_id=item.get('cardapioitem_id'),
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
async def criar_pix_cliente(payload: PagarNovoIn, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    if payload.usuario_id is not None or payload.origem_checkout != "CLIENT":
        raise HTTPException(status_code=403, detail="Origem de pagamento inválida")
    try:
        carrinho = get_carrinho(
            db, payload.cliente_id, payload.loja_id, payload.usuario_id
        )
        if not carrinho:
            raise HTTPException(status_code=404, detail='Carrinho nao encontrado')
        itens = carrinho.get('itens') or []
        if not itens:
            raise HTTPException(status_code=400, detail='Carrinho vazio')
        loja = db.query(Loja).filter(Loja.loja_id == payload.loja_id).first()
        if payload.entrega and (not loja or loja.permiteentrega != 'S'):
            raise HTTPException(status_code=400, detail='Este estabelecimento não aceita delivery.')
        carrinho_id = int(carrinho.get('carrinho_id') or 0)
        if not carrinho_id:
            raise HTTPException(status_code=400, detail='Carrinho invalido')

        agora = datetime.now()
        await _cancelar_tentativas_anteriores(db, carrinho_id)
        itens_recalculados, _ = _recalcular_itens_carrinho(db, itens, payload.loja_id, payload.organizacao_id)
        _, valor_total, valor_taxa = _montar_itens_asaas(itens_recalculados)
        valor_taxa = round(sum(float(item.get("vrtaxaitvenda") or 0) * int(item.get("qtitcarrinho") or 1) for item in itens_recalculados), 2)
        valor_cashback, debitos_cashback = reservar_uso(db, cliente_id=payload.cliente_id, organizacao_id=payload.organizacao_id, loja_id=payload.loja_id, total_produtos=valor_total, valor_solicitado=payload.valor_cashback) if payload.usar_cashback else (Decimal("0"), [])
        valor_cobrado = round(float(Decimal(str(valor_total)) - valor_cashback), 2)
        _exigir_valor_positivo(valor_cobrado)
        valor_taxa = round(valor_taxa * (valor_cobrado / valor_total), 2) if valor_total else 0
        external_reference = (
            f'PIX-{APP_ENV.upper()}-CLIENT-{carrinho_id}-{uuid.uuid4().hex[:12]}'
        )
        api_key_loja, wallet_loja = obter_conta_asaas_da_loja(db, payload.loja_id)
        campanha_doacao = obter_campanha_doacao_vigente(db, loja_id=payload.loja_id)
        campanha_doacao = validar_campanha_para_split(
            campanha_doacao, wallet_loja=wallet_loja
        )
        await garantir_webhook_pagamentos_asaas(api_key_loja)
        customer_id = await obter_ou_criar_customer_asaas_loja(
            db, cliente_id=payload.cliente_id, loja_id=payload.loja_id,
            api_key=api_key_loja,
        )
        cobranca = await criar_cobranca_pix_asaas(
            customer_id=customer_id,
            valor=valor_cobrado,
            descricao=f'Clubbar carrinho {carrinho_id}',
            external_reference=external_reference,
            api_key=api_key_loja,
            splits=montar_splits_pagamento(
                valor_taxa, campanha_doacao=campanha_doacao
            ),
            due_date=agora.date().isoformat(),
        )
        pagamento = cobranca['payment']
        qr = cobranca['qrCode']
        pix_id = str(pagamento['id'])
        registro = CheckoutAsaas(
            carrinho_id=carrinho_id,
            cliente_id=payload.cliente_id,
            loja_id=payload.loja_id,
            venda_id=None,
            checkout_id=pix_id,
            payment_id=pix_id,
            pix_qr_code_id=None,
            pix_payload=str(qr['payload']),
            pix_encoded_image=str(qr.get('encodedImage') or ''),
            pix_expiration_date=agora + timedelta(minutes=5),
            external_reference=external_reference,
            status='PENDING',
            valor=valor_cobrado,
            vrtaxaclubbar=valor_taxa,
            vrcashbackusado=valor_cashback,
            asaas_wallet_loja=wallet_loja,
            asaas_wallet_clubbar=ASAAS_CLUBBAR_WALLET_ID,
            dadosentrega=json.dumps(payload.entrega) if payload.entrega else None,
        )
        db.add(registro)
        db.flush()
        _salvar_snapshot_checkout(
            db,
            registro.checkout_asaas_id,
            itens_recalculados,
        )
        registrar_snapshot_doacao(
            db,
            checkout_asaas_id=registro.checkout_asaas_id,
            campanha=campanha_doacao,
        )
        vincular_uso_ao_checkout(db, debitos_cashback, registro)
        db.commit()
        return {
            'venda_id': None,
            'pagamento_id': pix_id,
            'pix_qr_code_id': None,
            'pix_copia_cola': qr['payload'],
            'encoded_image': qr.get('encodedImage'),
            'expiration_date': iso_utc(registro.pix_expiration_date),
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


@router.post('/pedido-entrega')
async def criar_pedido_entrega(
    payload: CriarPedidoEntregaIn,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Fecha o carrinho de produtos como um pedido com pagamento na entrega.

    O estado financeiro permanece PENDENTE. O entregador o confirma somente
    quando lê o QR Code do pedido no endereço do cliente.
    """
    exigir_cliente_autenticado(usuario, payload.cliente_id)

    loja = (
        db.query(Loja)
        .filter(
            Loja.loja_id == payload.loja_id,
            Loja.organizacao_id == payload.organizacao_id,
            Loja.sitloja == 'ATIVA',
        )
        .first()
    )
    if not loja:
        raise HTTPException(status_code=404, detail='Estabelecimento não encontrado ou indisponível.')
    if loja.permiteentrega != 'S':
        raise HTTPException(status_code=400, detail='Este estabelecimento não aceita delivery.')

    carrinho = get_carrinho(db, payload.cliente_id, payload.loja_id, None)
    if not carrinho or not carrinho.get('itens'):
        raise HTTPException(status_code=400, detail='Carrinho vazio')

    carrinho_id = int(carrinho.get('carrinho_id') or 0)
    if not carrinho_id:
        raise HTTPException(status_code=400, detail='Carrinho inválido')

    existente = (
        db.query(PedidoEntrega)
        .join(Venda, Venda.venda_id == PedidoEntrega.venda_id)
        .filter(
            Venda.carrinho_id == carrinho_id,
            Venda.cliente_id == payload.cliente_id,
        )
        .order_by(PedidoEntrega.pedidoentrega_id.desc())
        .first()
    )
    if existente:
        return {
            'pedidoentrega_id': int(existente.pedidoentrega_id),
            'venda_id': int(existente.venda_id),
            'situacao': existente.situacaopedido,
            'qrcode_token': existente.qrcode_token,
            'mensagem': 'Este pedido de entrega já foi criado.',
        }

    try:
        itens_recalculados, total = _recalcular_itens_carrinho(
            db,
            carrinho.get('itens') or [],
            payload.loja_id,
            payload.organizacao_id,
        )
        if not itens_recalculados:
            raise HTTPException(status_code=400, detail='Carrinho vazio')

        carrinho_para_venda = dict(carrinho)
        carrinho_para_venda['itens'] = itens_recalculados
        carrinho_para_venda['total'] = total
        venda_criada = await criar_ou_obter_venda_idempotente(
            db,
            cliente_id=payload.cliente_id,
            loja_id=payload.loja_id,
            organizacao_id=payload.organizacao_id,
            carrinho=carrinho_para_venda,
            plataforma='WEB',
            metodo_pagamento='OUTRO',
        )
        venda_id = int(venda_criada['venda_id'])
        venda = db.query(Venda).filter(Venda.venda_id == venda_id).first()
        pagamento = (
            db.query(PagVenda)
            .filter(PagVenda.venda_id == venda_id)
            .order_by(PagVenda.pagvenda_id.desc())
            .first()
        )
        if not venda or not pagamento:
            raise HTTPException(status_code=500, detail='Não foi possível preparar o pedido.')

        cidade, estado = resolver_localidade_entrega(
            db,
            cidade_informada=payload.cidade,
            uf_informada=payload.uf,
            loja=loja,
        )

        pagamento.dsmetodopag = 'PAGAMENTO_ENTREGA'
        pagamento.provedor = 'ENTREGA'
        pagamento.sitpagvenda = 'PENDENTE'
        pagamento.vrpagvenda = total
        venda.sitvenda = 'PENDENTE'
        venda.totalvenda = total

        pedido = PedidoEntrega(
            venda_id=venda_id,
            qrcode_token=gerar_token_qr(),
            situacaopedido='AGUARDANDO_ACEITE',
            cepentrega=payload.cep.strip(),
            enderecoentrega=payload.endereco.strip(),
            numeroentrega=payload.numero.strip(),
            complementoentrega=(payload.complemento or '').strip() or None,
            bairroentrega=payload.bairro.strip(),
            cidade_id=cidade.cidade_id,
            estado_id=estado.estado_id,
            cidadeentrega=cidade.nmcidade,
            ufentrega=estado.sgestado,
            observacaoentrega=(payload.observacao or '').strip() or None,
        )
        db.add(pedido)

        carrinho_db = db.query(Carrinho).filter(Carrinho.carrinho_id == carrinho_id).first()
        if carrinho_db:
            carrinho_db.sitcarrinho = 'FECHADO'
        db.commit()
        db.refresh(pedido)
        return {
            'pedidoentrega_id': int(pedido.pedidoentrega_id),
            'venda_id': venda_id,
            'situacao': pedido.situacaopedido,
            'qrcode_token': pedido.qrcode_token,
            'mensagem': 'Pedido enviado ao estabelecimento. Aguarde o aceite.',
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        print('[PEDIDO ENTREGA][ERRO]', repr(exc))
        raise HTTPException(status_code=500, detail='Não foi possível criar o pedido de entrega.')


@router.post("/pagar-asaas")
async def pagar_asaas_cliente(
    payload: PagarNovoIn,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    if payload.usuario_id is not None or payload.origem_checkout != "CLIENT":
        raise HTTPException(status_code=403, detail="Origem de pagamento inválida")
    return await pagar_asaas(payload, db)


async def pagar_asaas(
    payload: PagarNovoIn,
    db: Session = Depends(get_db),
):
    try:
        validar_publicacao_loja(db, payload.loja_id)
        loja = db.query(Loja).filter(Loja.loja_id == payload.loja_id).first()
        if payload.entrega and (not loja or loja.permiteentrega != 'S'):
            raise HTTPException(status_code=400, detail='Este estabelecimento não aceita delivery.')

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
            itens_car,
            payload.loja_id,
            payload.organizacao_id,
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

        validar_endereco_cobranca_para_cartao(cliente)

        api_key_loja, wallet_loja = obter_conta_asaas_da_loja(db, payload.loja_id)
        campanha_doacao = obter_campanha_doacao_vigente(db, loja_id=payload.loja_id)
        campanha_doacao = validar_campanha_para_split(
            campanha_doacao, wallet_loja=wallet_loja
        )
        await garantir_webhook_pagamentos_asaas(api_key_loja)
        external_reference = criar_referencia_checkout_asaas(carrinho_id)
        items_asaas, valor_total_com_taxa, valor_taxa_clubbar = _montar_itens_asaas(
            itens_recalculados
        )
        valor_cashback, debitos_cashback = reservar_uso(db, cliente_id=payload.cliente_id, organizacao_id=payload.organizacao_id, loja_id=payload.loja_id, total_produtos=valor_total_com_taxa, valor_solicitado=payload.valor_cashback) if payload.usar_cashback else (Decimal("0"), [])
        valor_cobrado = round(float(Decimal(str(valor_total_com_taxa)) - valor_cashback), 2)
        _exigir_valor_positivo(valor_cobrado)
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
            splits=montar_splits_pagamento(
                valor_taxa_clubbar,
                campanha_doacao=campanha_doacao,
                para_checkout=True,
            ),
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
            dadosentrega=json.dumps(payload.entrega) if payload.entrega else None,
        )

        db.add(novo)
        db.flush()
        registrar_snapshot_doacao(
            db,
            checkout_asaas_id=novo.checkout_asaas_id,
            campanha=campanha_doacao,
        )
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
    usuario: dict = Depends(get_usuario_logado),
):
    exigir_cliente_autenticado(usuario, cliente_id)
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
async def consultar_status_checkout_asaas(
    checkout_id: str,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    checkout = db.query(CheckoutAsaas).filter(CheckoutAsaas.checkout_id == checkout_id).first()
    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout Asaas nao encontrado")
    exigir_cliente_autenticado(usuario, checkout.cliente_id)
    return await status_checkout_asaas(checkout_id, db)


@router.post("/asaas/sandbox/confirmar/{checkout_id}")
async def confirmar_checkout_sandbox_asaas(
    checkout_id: str,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Rota autenticada para homologar PIX sem movimentar dinheiro real."""
    checkout = db.query(CheckoutAsaas).filter(CheckoutAsaas.checkout_id == checkout_id).first()
    if not checkout:
        raise HTTPException(status_code=404, detail="Checkout Asaas nao encontrado")
    exigir_cliente_autenticado(usuario, checkout.cliente_id)
    if not checkout.payment_id:
        raise HTTPException(status_code=422, detail="Esta tentativa não possui cobrança PIX")
    api_key_loja, _ = obter_conta_asaas_da_loja(db, checkout.loja_id)
    await confirmar_pagamento_sandbox_asaas(checkout.payment_id, api_key_loja)
    # A confirmação pode acionar o webhook antes desta resposta. Recarrega o
    # registro para não confundir uma venda já concluída com uma tentativa
    # substituída.
    db.refresh(checkout)
    return await status_checkout_asaas(checkout_id, db)


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
                'tipo_compra': 'INGRESSO'
                if getattr(checkout_consultado, 'reserva_ingresso_id', None)
                else 'PRODUTO',
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
        if getattr(checkout, "payment_id", None):
            pagamento = await buscar_pagamento_confirmado_por_id(
                checkout.payment_id, api_key_checkout
            )
        elif getattr(checkout, "pix_qr_code_id", None):
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
                    'tipo_compra': 'INGRESSO'
                    if getattr(checkout, 'reserva_ingresso_id', None)
                    else 'PRODUTO',
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
            if possui_snapshot:
                resultado_venda = await criar_venda_paga_por_checkout_snapshot(
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
                not checkout.reserva_ingresso_id
                and not resultado_venda.get('already_processed')
                and resultado_venda.get('venda_id')
            ):
                _enviar_confirmacao_produtos_sem_bloquear(
                    db, int(resultado_venda['venda_id'])
                )
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
        elif (
            checkout.payment_id
            and checkout.pix_expiration_date
            and checkout.pix_expiration_date <= datetime.now()
        ):
            await cancelar_pagamento_asaas(checkout.payment_id, api_key_checkout)
            checkout.status = "EXPIRED"
            cancelar_uso_pendente(db, checkout)
            db.commit()
            status_atual = "EXPIRED"
    pago = status_atual in {"PAID", "RECEIVED", "CONFIRMED"}
    return {
        "pagamento_id": checkout.checkout_id,
        "status": "PAGO" if pago else status_atual,
        "tipo_compra": "INGRESSO"
        if getattr(checkout, "reserva_ingresso_id", None)
        else "PRODUTO",
        "venda_id": checkout.venda_id if pago else None,
        "cashback_gerado": _valor_cashback_gerado(db, checkout.venda_id)
        if pago
        else 0.0,
    }


@router.post("/asaas/reconciliar-pendentes")
async def reconciliar_pagamentos_pendentes_asaas(
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    """Confere compras pagas enquanto o aplicativo estava fechado."""
    if payload.get("role") != "cliente":
        raise HTTPException(status_code=403, detail="Acesso exclusivo do cliente")
    try:
        cliente_id = int(payload.get("sub"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=403, detail="Cliente inválido") from exc

    pendentes = (
        db.query(CheckoutAsaas)
        .filter(
            CheckoutAsaas.cliente_id == cliente_id,
            CheckoutAsaas.venda_id.is_(None),
            CheckoutAsaas.status.notin_(["PAID", "CANCELLED", "CANCELED", "EXPIRED"]),
        )
        .order_by(CheckoutAsaas.checkout_asaas_id.asc())
        .limit(20)
        .all()
    )
    confirmados = []
    for checkout in pendentes:
        try:
            if checkout.reserva_ingresso_id:
                from app.routers.reservas_ingressos import status_reserva

                resultado = await status_reserva(
                    int(checkout.reserva_ingresso_id), cliente_id, db
                )
                status_pagamento = str(
                    resultado.get("status_pagamento") or ""
                ).upper()
            else:
                resultado = await status_checkout_asaas(checkout.checkout_id, db)
                status_pagamento = str(resultado.get("status") or "").upper()
            if status_pagamento == "PAGO":
                confirmados.append(
                    {
                        "pagamento_id": checkout.checkout_id,
                        "venda_id": resultado.get("venda_id"),
                    }
                )
        except HTTPException as exc:
            # Uma tentativa pendente não pode impedir a reconciliação das demais.
            db.rollback()
            print("[ASAAS RECONCILIACAO] Pendente não conciliado:", exc.detail)

    return {"ok": True, "pagamentos_confirmados": confirmados}
