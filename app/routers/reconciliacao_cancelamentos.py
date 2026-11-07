from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.cliente import Cliente
from app.models.eventolote import EventoLote
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.pagvenda import PagVenda
from app.models.venda import Venda
from app.services.asaas_service import consultar_pagamento_asaas
from app.services.asaas_split_service import obter_conta_asaas_da_loja
from app.services.cashback_service import cancelar_cashback_da_venda
from app.services.mercado_pago_service import obter_token_loja, buscar_pagamento_por_id


router = APIRouter(
    prefix="/reconciliacao-cancelamentos",
    tags=["Reconciliação de cancelamentos"],
)


def _organizacao_administradora(payload: dict) -> int:
    """Restringe a reconciliação financeira a administradores parceiros."""
    cargo = str(payload.get("dscargo") or "").strip().upper()
    if payload.get("role") != "usuario" or cargo not in {"SUPERADMIN", "ADMIN"}:
        raise HTTPException(
            status_code=403,
            detail="Somente administradores podem reconciliar cancelamentos.",
        )
    try:
        organizacao_id = int(payload.get("organizacao_id") or 0)
    except (TypeError, ValueError):
        organizacao_id = 0
    if organizacao_id <= 0:
        raise HTTPException(status_code=403, detail="Organização não identificada no login.")
    return organizacao_id


def _dinheiro(valor) -> float:
    return float(Decimal(str(valor or 0)).quantize(Decimal("0.01")))


def _valor_item(item: ItVenda) -> float:
    return _dinheiro(
        Decimal(str(item.vrunititvenda or 0)) * int(item.qtitvenda or 1)
        + Decimal(str(item.vrtaxaitvenda or 0))
    )


def _reativar_venda_sem_estorno(
    venda: Venda,
    itens: list[ItVenda],
    pagamento: PagVenda,
) -> None:
    """Restaura integralmente uma venda cujo estorno não foi registrado.

    O cancelamento é feito por transação. Portanto, ao desfazê-lo com
    segurança, venda, pagamento e todos os itens precisam voltar ao estado
    ativo; reativar somente os itens deixa a compra inutilizável ao cliente.
    """
    for item in itens:
        item.sititvenda = "ATIVO"
        item.dtcancelamento = None
        item.vrreembolso = None
        item.idreembolso = None
    venda.sitvenda = "PAGA"
    pagamento.sitpagvenda = "PAGO"


def _pagamento_da_venda(db: Session, venda_id: int) -> PagVenda:
    pagamento = (
        db.query(PagVenda)
        .filter(PagVenda.venda_id == venda_id)
        .order_by(PagVenda.pagvenda_id.desc())
        .first()
    )
    if not pagamento or not str(pagamento.idtransacaopagvenda or "").strip():
        raise HTTPException(
            status_code=409,
            detail="Esta venda não possui uma cobrança disponível para reconciliação.",
        )
    return pagamento


def _venda_em_processamento(
    db: Session,
    venda_id: int,
    organizacao_id: int,
) -> tuple[Venda, list[ItVenda], PagVenda]:
    venda = (
        db.query(Venda)
        .filter(Venda.venda_id == venda_id, Venda.organizacao_id == organizacao_id)
        .with_for_update()
        .first()
    )
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada.")

    itens = (
        db.query(ItVenda)
        .filter(ItVenda.venda_id == venda_id)
        .with_for_update()
        .all()
    )
    if not itens or not any(item.sititvenda == "CANCELAMENTO_SOLICITADO" for item in itens):
        raise HTTPException(
            status_code=409,
            detail="Esta venda não possui cancelamento aguardando reconciliação.",
        )

    # A compra é cancelada por transação. Não resolvemos manualmente uma venda
    # parcialmente alterada, pois não há como atribuir um estorno antigo a um
    # item específico com segurança.
    if any(item.sititvenda != "CANCELAMENTO_SOLICITADO" for item in itens):
        raise HTTPException(
            status_code=409,
            detail=(
                "Esta venda possui itens em situações diferentes e precisa ser "
                "avaliada pelo suporte financeiro."
            ),
        )
    return venda, itens, _pagamento_da_venda(db, venda_id)


async def _consultar_estorno(db: Session, venda: Venda, pagamento: PagVenda) -> dict:
    if str(pagamento.provedor or 'ASAAS').upper() != 'ASAAS':
        raise HTTPException(409, 'Esta venda não foi paga pelo Asaas.')
    api_key, _ = obter_conta_asaas_da_loja(db, venda.loja_id)
    retorno = await consultar_pagamento_asaas(
        str(pagamento.idtransacaopagvenda),
        api_key,
    )
    estornos = []
    for estorno in retorno.get("refunds") or []:
        if not isinstance(estorno, dict):
            continue
        if str(estorno.get("status") or "").upper() == "CANCELLED":
            continue
        estornos.append(
            {
                "id": str(estorno.get("id") or "") or None,
                "valor": _dinheiro(estorno.get("value")),
                "status": str(estorno.get("status") or "PROCESSANDO").upper(),
                "data": estorno.get("dateCreated") or estorno.get("date"),
            }
        )
    return {
        "pagamento_id": str(pagamento.idtransacaopagvenda),
        "valor_cobrado": _dinheiro(retorno.get("value") or pagamento.vrpagvenda),
        "valor_estornado": _dinheiro(sum(Decimal(str(item["valor"])) for item in estornos if item['status'] == 'DONE')),
        "estorno_pendente": any(item['status'] != 'DONE' for item in estornos),
        "estornos": estornos,
    }


async def _consultar_estorno_mercado_pago(db: Session, venda: Venda, pagamento: PagVenda) -> dict:
    if str(pagamento.provedor or '').upper() != 'MERCADO_PAGO':
        raise HTTPException(409, 'Esta venda não foi paga pelo Mercado Pago.')
    if not pagamento.lojamercadopago_id:
        raise HTTPException(409, 'A conta original do Mercado Pago não foi identificada.')
    token, _ = await obter_token_loja(db, venda.loja_id, pagamento.lojamercadopago_id)
    retorno = await buscar_pagamento_por_id(access_token=token, payment_id=str(pagamento.idtransacaopagvenda))
    if not retorno:
        raise HTTPException(404, 'Pagamento não encontrado no Mercado Pago.')
    valor_cobrado = _dinheiro(retorno.get('transaction_amount'))
    valor_estornado = _dinheiro(retorno.get('transaction_amount_refunded'))
    status = str(retorno.get('status') or '').lower()
    estornos = retorno.get('refunds') or []
    return {
        'pagamento_id': str(pagamento.idtransacaopagvenda),
        'valor_cobrado': valor_cobrado,
        'valor_estornado': valor_estornado,
        'estornos': [{'id': str(item.get('id') or '') or None} for item in estornos if isinstance(item, dict)],
        'estorno_localizado': status == 'refunded' and valor_cobrado > 0 and valor_estornado >= valor_cobrado,
        'status_pagamento': status,
    }


def _resumo_venda(db: Session, venda: Venda) -> dict:
    itens = db.query(ItVenda).filter(ItVenda.venda_id == venda.venda_id).all()
    pendentes = [item for item in itens if item.sititvenda == "CANCELAMENTO_SOLICITADO"]
    pagamento = _pagamento_da_venda(db, venda.venda_id)
    loja = db.query(Loja).filter(Loja.loja_id == venda.loja_id).first()
    cliente = db.query(Cliente).filter(Cliente.cliente_id == venda.cliente_id).first()
    ultimo_movimento = max(
        (item.dtultatu or item.dtcriacao for item in pendentes),
        default=venda.dtultatu or venda.dtcriacao,
    )
    tipos = sorted({str(item.tipoitem or "").capitalize() for item in pendentes})
    return {
        "venda_id": int(venda.venda_id),
        "loja": loja.nmloja if loja else "Estabelecimento",
        "cliente": cliente.nmcliente if cliente else "Cliente não identificado",
        "data_venda": venda.dtcriacao,
        "ultimo_movimento": ultimo_movimento,
        "quantidade_itens": len(pendentes),
        "tipos_itens": tipos,
        "valor_esperado": _dinheiro(sum(Decimal(str(_valor_item(item))) for item in pendentes)),
        "pagamento_id": str(pagamento.idtransacaopagvenda),
    }


@router.get("")
def listar(
    limite: int = Query(default=100, ge=1, le=300),
    provedor: str = Query(default='ASAAS', pattern='^(ASAAS|MERCADO_PAGO)$'),
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _organizacao_administradora(payload)
    vendas = (
        db.query(Venda)
        .join(ItVenda, ItVenda.venda_id == Venda.venda_id)
        .join(PagVenda, PagVenda.venda_id == Venda.venda_id)
        .filter(
            Venda.organizacao_id == organizacao_id,
            ItVenda.sititvenda == "CANCELAMENTO_SOLICITADO",
            func.coalesce(PagVenda.provedor, 'ASAAS') == provedor,
            PagVenda.pagvenda_id == select(func.max(PagVenda.pagvenda_id)).where(PagVenda.venda_id == Venda.venda_id).correlate(Venda).scalar_subquery(),
        )
        .distinct()
        .order_by(Venda.dtultatu.desc(), Venda.dtcriacao.desc())
        .limit(limite)
        .all()
    )
    return [_resumo_venda(db, venda) for venda in vendas]


@router.get('/{venda_id}/mercado-pago')
async def consultar_mercado_pago(venda_id: int, payload: dict = Depends(get_usuario_logado), db: Session = Depends(get_db)):
    organizacao_id = _organizacao_administradora(payload)
    venda, itens, pagamento = _venda_em_processamento(db, venda_id, organizacao_id)
    consulta = await _consultar_estorno_mercado_pago(db, venda, pagamento)
    consulta['valor_esperado'] = _dinheiro(sum(Decimal(str(_valor_item(item))) for item in itens))
    return consulta


@router.get("/{venda_id}/asaas")
async def consultar_asaas(
    venda_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _organizacao_administradora(payload)
    venda, itens, pagamento = _venda_em_processamento(db, venda_id, organizacao_id)
    consulta = await _consultar_estorno(db, venda, pagamento)
    valor_esperado = _dinheiro(sum(Decimal(str(_valor_item(item))) for item in itens))
    consulta["valor_esperado"] = valor_esperado
    consulta["estorno_localizado"] = consulta["valor_estornado"] >= valor_esperado and not consulta['estorno_pendente']
    return consulta


@router.post("/{venda_id}/concluir")
async def concluir(
    venda_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _organizacao_administradora(payload)
    venda, itens, pagamento = _venda_em_processamento(db, venda_id, organizacao_id)
    mercado_pago = str(pagamento.provedor or '').upper() == 'MERCADO_PAGO'
    pagamento_id = pagamento.pagvenda_id
    consulta = await (_consultar_estorno_mercado_pago(db, venda, pagamento) if mercado_pago else _consultar_estorno(db, venda, pagamento))
    if mercado_pago:
        # A renovação do token pode fazer commit e liberar os bloqueios.
        venda, itens, pagamento = _venda_em_processamento(db, venda_id, organizacao_id)
        if pagamento.pagvenda_id != pagamento_id:
            raise HTTPException(409, 'O pagamento da venda foi alterado. Consulte novamente.')
    valor_esperado = _dinheiro(sum(Decimal(str(_valor_item(item))) for item in itens))
    if (mercado_pago and not consulta['estorno_localizado']) or (not mercado_pago and (consulta["valor_estornado"] < valor_esperado or consulta['estorno_pendente'])):
        raise HTTPException(
            status_code=409,
            detail="O provedor ainda não confirmou o estorno integral desta transação.",
        )

    estorno_id = next((item["id"] for item in consulta["estornos"] if item["id"] and (mercado_pago or item.get('status') == 'DONE')), None)
    lotes_cancelados: dict[int, int] = {}
    saldo_a_distribuir = valor_esperado
    for indice, item in enumerate(itens):
        valor_item = _valor_item(item)
        reembolso_item = (
            saldo_a_distribuir
            if indice == len(itens) - 1
            else min(valor_item, saldo_a_distribuir)
        )
        saldo_a_distribuir = _dinheiro(max(0, saldo_a_distribuir - reembolso_item))
        item.sititvenda = "CANCELADO"
        item.dtcancelamento = datetime.now()
        item.vrreembolso = reembolso_item
        item.idreembolso = estorno_id
        if item.lote_id:
            lotes_cancelados[item.lote_id] = lotes_cancelados.get(item.lote_id, 0) + int(item.qtitvenda or 1)

    for lote_id, quantidade in lotes_cancelados.items():
        lote = db.query(EventoLote).filter(EventoLote.lote_id == lote_id).first()
        if lote and lote.qtvendidalote:
            lote.qtvendidalote = max(0, int(lote.qtvendidalote) - quantidade)

    venda.sitvenda = "CANCELADA"
    pagamento.sitpagvenda = "CANCELADO"
    cancelar_cashback_da_venda(db, venda.venda_id)
    db.commit()
    return {"ok": True, "mensagem": "Cancelamento concluído após confirmação do provedor."}


@router.post("/{venda_id}/reativar")
async def reativar(
    venda_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    organizacao_id = _organizacao_administradora(payload)
    venda, itens, pagamento = _venda_em_processamento(db, venda_id, organizacao_id)
    consulta = await _consultar_estorno(db, venda, pagamento)
    if consulta["valor_estornado"] > 0 or consulta['estorno_pendente']:
        raise HTTPException(
            status_code=409,
            detail=(
                "O Asaas possui estorno registrado para esta venda. "
                "Conclua o cancelamento; não é seguro reativar os itens."
            ),
        )
    _reativar_venda_sem_estorno(venda, itens, pagamento)
    db.commit()
    return {
        "ok": True,
        "mensagem": "Compra reativada: o Asaas não registrou estorno.",
    }
