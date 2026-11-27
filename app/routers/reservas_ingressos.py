import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_usuario_logado
from app.core.cliente_auth import exigir_cliente_autenticado
from app.models.reserva_ingresso import ReservaIngresso
from app.models.reserva_ingresso_participante import ReservaIngressoParticipante
from app.models.compra_evento import CompraEvento, CompraEventoItem
from app.models.checkout_asaas import CheckoutAsaas
from app.models.checkout_mercadopago import CheckoutMercadoPago
from app.models.cliente import Cliente
from app.models.loja import Loja
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventolote import EventoLote
from app.schemas.reserva_ingresso import ReservaIngressoCreate, ReservaIngressoGrupoCreate, ItemReservaIngressoCreate, ParticipanteReservaIn, ParticipantesReservaUpdate, PagamentoReservaIn
from app.services.reserva_ingresso_service import criar_reserva, beneficios_validos_para_reserva
from app.services.asaas_service import criar_checkout_asaas, criar_cobranca_pix_asaas, obter_ou_criar_customer_asaas_loja, buscar_pagamento_confirmado_por_id, buscar_pagamento_confirmado_por_checkout, buscar_pagamento_confirmado_por_qrcode_pix, buscar_pagamento_confirmado_por_referencia, cancelar_pagamento_asaas, validar_endereco_cobranca_para_cartao
from app.services.venda_reserva_ingresso_service import finalizar_reserva_paga, finalizar_reserva_gratuita
from app.services.notificacao_ingressos_service import enviar_ingressos_confirmados_da_venda
from app.services.cortesia_evento_service import (
    bloquear_evento_para_cortesia,
    validar_cortesia_unica_por_cpf,
)
from app.core.config import APP_ENV, ASAAS_API_KEY, ASAAS_CLUBBAR_WALLET_ID
from app.services.asaas_split_service import obter_conta_asaas_da_loja, montar_splits_pagamento
from app.services.asaas_webhook_service import garantir_webhook_pagamentos_asaas
from app.services.mercado_pago_service import (
    buscar_pagamento_por_referencia as buscar_pagamento_mercado_pago,
    criar_pagamento_pix as criar_pagamento_pix_mercado_pago,
    criar_pagamento_cartao as criar_pagamento_cartao_mercado_pago,
    buscar_pagamento_por_id as buscar_pagamento_mp_por_id,
    obter_token_loja as obter_token_mercado_pago_loja,
)
from app.services.campanha_doacao_service import (
    obter_campanha_para_reserva,
    registrar_snapshot_doacao,
    validar_campanha_para_split,
)
from app.utils.datetime_utils import iso_utc, FUSO_BRASIL
from app.services.reserva_mercado_pago_service import confirmar_pagamento_reserva_mp
from app.services.taxa_processamento_ingresso import cotar_ingressos_mercado_pago, cotar_itens_mercado_pago

router = APIRouter(prefix="/reservas-ingressos", tags=["Reservas de ingressos"])
PIX_ASAAS_INGRESSOS_ATIVO = False


def _eh_cortesia(db: Session, lotepreco_id: int) -> bool:
    preco = db.query(EventoLotePreco).filter(
        EventoLotePreco.lotepreco_id == lotepreco_id
    ).first()
    return bool(preco and ((preco.tipopreco or "").strip().upper() == "CORTESIA" or Decimal(str(preco.vrpreco or 0)) <= 0))


def _grupo(db: Session, reserva: ReservaIngresso) -> list[ReservaIngresso]:
    compra_evento_id = getattr(reserva, 'compra_evento_id', None)
    if compra_evento_id:
        return db.query(ReservaIngresso).filter(
            ReservaIngresso.compra_evento_id == compra_evento_id,
            ReservaIngresso.sitreserva.in_(('PREENCHENDO', 'AGUARDANDO_PAGAMENTO')),
        ).order_by(ReservaIngresso.reserva_ingresso_id).all()
    return [reserva]


def _valor_grupo(db: Session, reserva: ReservaIngresso) -> Decimal:
    return sum((Decimal(str(item.vrtotal or 0)) for item in _grupo(db, reserva)), Decimal("0")).quantize(Decimal("0.01"))


def _taxa_grupo(db: Session, reserva: ReservaIngresso) -> Decimal:
    return sum((Decimal(str(item.vrtaxa or 0)) * int(item.qtreservada or 0) for item in _grupo(db, reserva)), Decimal("0")).quantize(Decimal("0.01"))


def _beneficio_saida(beneficio) -> dict:
    return {
        "beneficio_id": beneficio.beneficio_id,
        "cdbeneficio": beneficio.cdbeneficio,
        "nmbeneficio": beneficio.nmbeneficio,
        "exigecomprovante": bool(beneficio.exigecomprovante),
    }


def _saida(db: Session, reserva: ReservaIngresso) -> dict:
    # A relação de benefícios precisa ser a mesma que será validada quando os
    # participantes forem informados. Assim o app não exibe uma opção antiga
    # ou pertencente a outra modalidade e depois a recusa no checkout.
    beneficios_validos = beneficios_validos_para_reserva(db, reserva)
    lote = db.query(EventoLote).filter(EventoLote.lote_id == reserva.lote_id).first()
    preco = db.query(EventoLotePreco).filter(EventoLotePreco.lotepreco_id == reserva.lotepreco_id).first()
    participantes = db.query(ReservaIngressoParticipante).filter(
        ReservaIngressoParticipante.reserva_ingresso_id == reserva.reserva_ingresso_id
    ).order_by(ReservaIngressoParticipante.ordem).all()
    return {
        "participantes": [{"nome": p.nmparticipante, "cpf": p.cpfparticipante,
                           "beneficio_id": p.beneficio_id} for p in participantes],
        "reserva_ingresso_id": reserva.reserva_ingresso_id,
        "organizacao_id": reserva.organizacao_id,
        "loja_id": reserva.loja_id,
        "cliente_id": reserva.cliente_id,
        "evento_id": reserva.evento_id,
        "lote_id": reserva.lote_id,
        "lotepreco_id": reserva.lotepreco_id,
        "beneficio_id": getattr(reserva, "beneficio_id", None),
        "tipo_beneficio": reserva.tipobeneficio,
        "quantidade": reserva.qtreservada,
        "valor_unitario": float(reserva.vrunitario),
        "percentual_taxa": float(reserva.pctaxa),
        "valor_taxa_unitaria": float(reserva.vrtaxa),
        "valor_total": float(reserva.vrtotal),
        "status": reserva.sitreserva,
        "data_expiracao": iso_utc(reserva.dtexpiracao),
        "segundos_restantes": max(0, int((reserva.dtexpiracao - datetime.now()).total_seconds())),
        "venda_id": reserva.venda_id,
        "nome_lote": (
            f"Lote {lote.lote_global.nrlote}"
            if lote and getattr(lote, "lote_global", None) and lote.lote_global.nrlote is not None
            else "Lote"
        ),
        "nome_setor": getattr(getattr(lote, "setor", None), "nmsetor", None),
        "nome_modalidade": getattr(preco, "nmpreco", None),
        "exige_beneficio": bool(beneficios_validos),
        "beneficios_validos": [
            _beneficio_saida(beneficio)
            for beneficio in beneficios_validos.values()
        ],
    }


@router.post("")
def reservar(payload: ReservaIngressoCreate, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    try:
        reserva = criar_reserva(db, cliente_id=payload.cliente_id, lote_id=payload.lote_id, lotepreco_id=payload.lotepreco_id, beneficio_id=payload.beneficio_id, tipo_beneficio=payload.tipo_beneficio, quantidade=payload.quantidade)
        db.commit()
        db.refresh(reserva)
        return _saida(db, reserva)
    except HTTPException:
        db.rollback()
        raise


@router.post("/grupo")
def reservar_grupo(payload: ReservaIngressoGrupoCreate, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    if sum(item.quantidade for item in payload.itens) > 5:
        raise HTTPException(422, "O limite é de 5 ingressos por transação.")
    quantidade_cortesias = sum(
        item.quantidade for item in payload.itens
        if _eh_cortesia(db, item.lotepreco_id)
    )
    if quantidade_cortesias > 2:
        raise HTTPException(422, "O limite é de 2 cortesias por transação.")
    try:
        reservas = []
        compra = None
        for item in payload.itens:
            for _ in range(item.quantidade):
                reserva = criar_reserva(db, cliente_id=payload.cliente_id, lote_id=item.lote_id,
                    lotepreco_id=item.lotepreco_id, beneficio_id=item.beneficio_id,
                    tipo_beneficio=item.tipo_beneficio, quantidade=1)
                reservas.append(reserva)
        principal = reservas[0]
        if any(item.evento_id != principal.evento_id or item.loja_id != principal.loja_id for item in reservas):
            raise HTTPException(409, "Selecione ingressos de um único evento e estabelecimento.")
        compra = CompraEvento(
            organizacao_id=principal.organizacao_id, loja_id=principal.loja_id,
            cliente_id=principal.cliente_id, evento_id=principal.evento_id,
            valor_total=sum((Decimal(str(item.vrtotal)) for item in reservas), Decimal("0")),
            dtexpiracao=min(item.dtexpiracao for item in reservas),
        )
        db.add(compra)
        db.flush()
        for item in reservas:
            item.dtexpiracao = compra.dtexpiracao
            item.compra_evento_id = compra.compra_evento_id
            db.add(CompraEventoItem(
                compra_evento_id=compra.compra_evento_id, tipoitem="INGRESSO",
                reserva_ingresso_id=item.reserva_ingresso_id, quantidade=item.qtreservada,
                valor_unitario=item.vrunitario, valor_taxa=item.vrtaxa,
                subtotal=item.vrtotal,
            ))
        db.commit()
        for reserva in reservas: db.refresh(reserva)
        resposta = _saida(db, principal)
        resposta["compra_evento_id"] = compra.compra_evento_id
        resposta["itens"] = [_saida(db, item) for item in reservas]
        resposta["quantidade"] = sum(item.qtreservada for item in reservas)
        resposta["valor_total"] = float(sum((Decimal(str(item.vrtotal)) for item in reservas), Decimal("0")))
        return resposta
    except Exception:
        db.rollback()
        raise


class ResgateDiretoIn(ReservaIngressoCreate):
    participante: ParticipanteReservaIn


@router.post("/resgate-cortesia")
def resgatar_cortesia_direta(payload: ResgateDiretoIn, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    """Reserva e resgata uma única cortesia em uma transação, sem sacola."""
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    if payload.quantidade != 1:
        raise HTTPException(422, "Resgate uma cortesia por vez.")
    try:
        if not _eh_cortesia(db, payload.lotepreco_id):
            raise HTTPException(422, "Esta modalidade não é uma cortesia.")
        reserva = criar_reserva(db, cliente_id=payload.cliente_id, lote_id=payload.lote_id,
            lotepreco_id=payload.lotepreco_id, beneficio_id=payload.beneficio_id,
            tipo_beneficio=payload.tipo_beneficio, quantidade=1)
        if Decimal(str(reserva.vrtotal or 0)) != 0:
            raise HTTPException(409, "A cortesia deve ter valor zero.")
        return informar_participantes(reserva.reserva_ingresso_id,
            ParticipantesReservaUpdate(participantes=[payload.participante]), db, usuario)
    except Exception:
        db.rollback()
        raise


@router.post("/compra-evento")
def criar_compra_evento_item(payload: ItemReservaIngressoCreate, cliente_id: int, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    """Adiciona o primeiro ingresso à sacola temporária do evento."""
    exigir_cliente_autenticado(usuario, cliente_id)
    try:
        if _eh_cortesia(db, payload.lotepreco_id) and payload.quantidade > 2:
            raise HTTPException(422, "O limite é de 2 cortesias por transação.")
        reservas = [
            criar_reserva(db, cliente_id=cliente_id, lote_id=payload.lote_id,
                lotepreco_id=payload.lotepreco_id, beneficio_id=payload.beneficio_id,
                tipo_beneficio=payload.tipo_beneficio, quantidade=1)
            for _ in range(payload.quantidade)
        ]
        principal = reservas[0]
        total = sum((Decimal(str(item.vrtotal)) for item in reservas), Decimal("0"))
        compra = CompraEvento(
            organizacao_id=principal.organizacao_id, loja_id=principal.loja_id,
            cliente_id=cliente_id, evento_id=principal.evento_id,
            valor_total=total, dtexpiracao=min(item.dtexpiracao for item in reservas),
        )
        db.add(compra); db.flush()
        for reserva in reservas:
            reserva.dtexpiracao = compra.dtexpiracao
            reserva.compra_evento_id = compra.compra_evento_id
            db.add(CompraEventoItem(
                compra_evento_id=compra.compra_evento_id, tipoitem="INGRESSO",
                reserva_ingresso_id=reserva.reserva_ingresso_id, quantidade=1,
                valor_unitario=reserva.vrunitario, valor_taxa=reserva.vrtaxa,
                subtotal=reserva.vrtotal,
            ))
        db.commit()
        for reserva in reservas:
            db.refresh(reserva)
        resposta = _saida(db, principal)
        resposta["compra_evento_id"] = compra.compra_evento_id
        resposta["itens"] = [_saida(db, reserva) for reserva in reservas]
        resposta["quantidade"] = len(reservas)
        resposta["valor_total"] = float(total)
        return resposta
    except Exception:
        db.rollback(); raise


@router.post("/compra-evento/{compra_evento_id}/ingressos")
def adicionar_ingresso_compra_evento(compra_evento_id: int, payload: ItemReservaIngressoCreate, cliente_id: int, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    exigir_cliente_autenticado(usuario, cliente_id)
    compra = db.query(CompraEvento).filter(
        CompraEvento.compra_evento_id == compra_evento_id,
        CompraEvento.cliente_id == cliente_id,
        CompraEvento.status == "ABERTA",
    ).with_for_update().first()
    if not compra:
        raise HTTPException(404, "Compra de evento não encontrada")
    if compra.dtexpiracao <= datetime.now():
        raise HTTPException(409, "A reserva de ingressos expirou")
    if _eh_cortesia(db, payload.lotepreco_id):
        reservas_atuais = db.query(ReservaIngresso).filter(
            ReservaIngresso.compra_evento_id == compra_evento_id,
            ReservaIngresso.sitreserva.in_(("PREENCHENDO", "AGUARDANDO_PAGAMENTO")),
        ).all()
        quantidade_cortesias = sum(
            int(item.qtreservada or 0)
            for item in reservas_atuais
            if _eh_cortesia(db, item.lotepreco_id)
        )
        if quantidade_cortesias + payload.quantidade > 2:
            raise HTTPException(422, "O limite é de 2 cortesias por transação.")
    try:
        reservas_novas = []
        for _ in range(int(payload.quantidade)):
            reserva_item = criar_reserva(
                db, cliente_id=cliente_id, lote_id=payload.lote_id,
                lotepreco_id=payload.lotepreco_id, beneficio_id=payload.beneficio_id,
                tipo_beneficio=payload.tipo_beneficio, quantidade=1,
            )
            if reserva_item.evento_id != compra.evento_id or reserva_item.loja_id != compra.loja_id:
                raise HTTPException(409, "O ingresso pertence a outro evento ou estabelecimento")
            reserva_item.compra_evento_id = compra_evento_id
            reserva_item.dtexpiracao = compra.dtexpiracao
            reservas_novas.append(reserva_item)
            db.add(CompraEventoItem(
                compra_evento_id=compra_evento_id, tipoitem="INGRESSO",
                reserva_ingresso_id=reserva_item.reserva_ingresso_id, quantidade=1,
                valor_unitario=reserva_item.vrunitario, valor_taxa=reserva_item.vrtaxa,
                subtotal=reserva_item.vrtotal,
            ))
        compra.valor_total = Decimal(str(compra.valor_total or 0)) + sum(
            (Decimal(str(item.vrtotal or 0)) for item in reservas_novas), Decimal("0")
        )
        compra.dtexpiracao = min(
            compra.dtexpiracao,
            *(item.dtexpiracao for item in reservas_novas),
        )
        reserva = reservas_novas[-1]
        db.commit(); db.refresh(reserva)
        itens = _grupo(db, reserva)
        resposta = _saida(db, reserva)
        resposta["compra_evento_id"] = compra_evento_id
        resposta["itens"] = [_saida(db, item) for item in itens]
        resposta["quantidade"] = sum(item.qtreservada for item in itens)
        resposta["valor_total"] = float(sum((Decimal(str(item.vrtotal)) for item in itens), Decimal("0")))
        return resposta
    except Exception:
        db.rollback(); raise


@router.post("/compra-evento/{compra_evento_id}/ingressos-grupo")
def adicionar_grupo_compra_evento(compra_evento_id: int, payload: ReservaIngressoGrupoCreate,
                                 db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    """Inclui a seleção inteira na mesma transação e preserva o prazo original."""
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    try:
        compra = db.query(CompraEvento).filter(
            CompraEvento.compra_evento_id == compra_evento_id,
            CompraEvento.cliente_id == payload.cliente_id,
            CompraEvento.status == "ABERTA",
        ).with_for_update().first()
        if not compra:
            raise HTTPException(404, "Compra de evento não encontrada")
        if compra.dtexpiracao <= datetime.now():
            raise HTTPException(409, "A reserva de ingressos expirou")
        existentes = db.query(ReservaIngresso).filter(
            ReservaIngresso.compra_evento_id == compra_evento_id,
            ReservaIngresso.sitreserva.in_(("PREENCHENDO", "AGUARDANDO_PAGAMENTO")),
        ).all()
        ids = [item.reserva_ingresso_id for item in existentes]
        if ids and (
            db.query(CheckoutMercadoPago).filter(
                CheckoutMercadoPago.reserva_ingresso_id.in_(ids),
                CheckoutMercadoPago.status.in_(("CREATING", "PENDING", "APPROVED", "PAID")),
            ).first()
            or db.query(CheckoutAsaas).filter(
                CheckoutAsaas.reserva_ingresso_id.in_(ids),
                CheckoutAsaas.status.in_(("PENDING", "ACTIVE", "CONFIRMED", "RECEIVED")),
            ).first()
        ):
            raise HTTPException(409, "Já existe um pagamento para esta reserva. Confira o pagamento antes de alterar os ingressos.")
        quantidade = sum(int(item.qtreservada or 0) for item in existentes)
        if quantidade + sum(item.quantidade for item in payload.itens) > 5:
            raise HTTPException(422, "O limite é de 5 ingressos por transação.")
        if any(_eh_cortesia(db, item.lotepreco_id) for item in payload.itens):
            raise HTTPException(422, "Resgate cortesias individualmente.")
        for item in payload.itens:
            for _ in range(item.quantidade):
                reserva = criar_reserva(db, cliente_id=payload.cliente_id, lote_id=item.lote_id,
                    lotepreco_id=item.lotepreco_id, beneficio_id=item.beneficio_id,
                    tipo_beneficio=item.tipo_beneficio, quantidade=1)
                if reserva.evento_id != compra.evento_id or reserva.loja_id != compra.loja_id:
                    raise HTTPException(409, "O ingresso pertence a outro evento ou estabelecimento")
                reserva.compra_evento_id = compra_evento_id
                reserva.dtexpiracao = compra.dtexpiracao
                db.add(CompraEventoItem(compra_evento_id=compra_evento_id, tipoitem="INGRESSO",
                    reserva_ingresso_id=reserva.reserva_ingresso_id, quantidade=1,
                    valor_unitario=reserva.vrunitario, valor_taxa=reserva.vrtaxa, subtotal=reserva.vrtotal))
                existentes.append(reserva)
        compra.valor_total = sum((Decimal(str(item.vrtotal or 0)) for item in existentes), Decimal("0"))
        db.commit()
        principal = existentes[0]
        resposta = _saida(db, principal)
        resposta.update(compra_evento_id=compra_evento_id,
            itens=[_saida(db, item) for item in existentes],
            quantidade=sum(item.qtreservada for item in existentes), valor_total=float(compra.valor_total))
        return resposta
    except Exception:
        db.rollback()
        raise


def _impedir_alteracao_com_pagamento(db: Session, reserva: ReservaIngresso) -> None:
    ids = [item.reserva_ingresso_id for item in _grupo(db, reserva)]
    if not ids:
        ids = [reserva.reserva_ingresso_id]
    pagamento_mp = db.query(CheckoutMercadoPago).filter(
        CheckoutMercadoPago.reserva_ingresso_id.in_(ids),
        CheckoutMercadoPago.status.in_(("CREATING", "PENDING", "APPROVED", "PAID")),
    ).first()
    pagamento_asaas = db.query(CheckoutAsaas).filter(
        CheckoutAsaas.reserva_ingresso_id.in_(ids),
        CheckoutAsaas.status.in_(("PENDING", "ACTIVE", "CONFIRMED", "RECEIVED")),
    ).first()
    if pagamento_mp or pagamento_asaas:
        raise HTTPException(409, "Já existe um pagamento para esta reserva. Confira o pagamento antes de alterar os ingressos.")


@router.delete("/compra-evento/{compra_evento_id}/ingressos/{reserva_id}")
def remover_ingresso_compra_evento(compra_evento_id: int, reserva_id: int, cliente_id: int, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    exigir_cliente_autenticado(usuario, cliente_id)
    compra = db.query(CompraEvento).filter(
        CompraEvento.compra_evento_id == compra_evento_id,
        CompraEvento.cliente_id == cliente_id,
        CompraEvento.status == "ABERTA",
    ).with_for_update().first()
    reserva = db.query(ReservaIngresso).filter(
        ReservaIngresso.reserva_ingresso_id == reserva_id,
        ReservaIngresso.compra_evento_id == compra_evento_id,
        ReservaIngresso.cliente_id == cliente_id,
    ).with_for_update().first()
    if not compra or not reserva:
        raise HTTPException(404, "Item da compra não encontrado")
    _impedir_alteracao_com_pagamento(db, reserva)
    db.query(CompraEventoItem).filter(
        CompraEventoItem.compra_evento_id == compra_evento_id,
        CompraEventoItem.reserva_ingresso_id == reserva_id,
    ).delete(synchronize_session=False)
    db.query(ReservaIngressoParticipante).filter(
        ReservaIngressoParticipante.reserva_ingresso_id == reserva_id,
    ).delete(synchronize_session=False)
    reserva.sitreserva = "CANCELADA"
    # A sessão usa autoflush=False: a consulta deve refletir o cancelamento.
    db.flush()
    restante = db.query(ReservaIngresso).filter(
        ReservaIngresso.compra_evento_id == compra_evento_id,
        ReservaIngresso.sitreserva.in_(("PREENCHENDO", "AGUARDANDO_PAGAMENTO")),
    ).all()
    if restante:
        compra.valor_total = sum((Decimal(str(item.vrtotal)) for item in restante), Decimal("0"))
    else:
        compra.valor_total = Decimal("0")
        compra.status = "CANCELADA"
    db.commit()
    return {
        "ok": True,
        "compra_evento_id": compra_evento_id,
        "valor_total": float(compra.valor_total),
        "quantidade": sum(item.qtreservada for item in restante),
        "itens": [_saida(db, item) for item in restante],
    }


@router.put("/{reserva_id}/participante")
def salvar_participante_individual(reserva_id: int, payload: ParticipanteReservaIn, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id).first()
    if not reserva:
        raise HTTPException(404, "Reserva não encontrada")
    exigir_cliente_autenticado(usuario, reserva.cliente_id)
    if reserva.compra_evento_id:
        compra = db.query(CompraEvento).filter(
            CompraEvento.compra_evento_id == reserva.compra_evento_id,
            CompraEvento.cliente_id == reserva.cliente_id,
            CompraEvento.status == "ABERTA",
        ).with_for_update().first()
        if not compra:
            raise HTTPException(409, "Compra não está disponível para edição")
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id).with_for_update().first()
    if not reserva or reserva.sitreserva not in {"PREENCHENDO", "AGUARDANDO_PAGAMENTO"} or reserva.dtexpiracao <= datetime.now():
        raise HTTPException(409, "A reserva de ingressos expirou ou não está disponível")
    if reserva.qtreservada != 1:
        raise HTTPException(409, "Esta reserva não corresponde a um ingresso individual")
    nome = payload.nome.strip()
    if len(nome) < 3:
        raise HTTPException(422, "Informe o nome completo do participante")
    grupo = _grupo(db, reserva)
    ids = [item.reserva_ingresso_id for item in grupo]
    duplicado = db.query(ReservaIngressoParticipante).filter(
        ReservaIngressoParticipante.reserva_ingresso_id.in_(ids),
        ReservaIngressoParticipante.reserva_ingresso_id != reserva_id,
        ReservaIngressoParticipante.cpfparticipante == payload.cpf,
    ).first()
    if duplicado:
        raise HTTPException(422, "Cada participante deve possuir um CPF distinto")
    beneficios = beneficios_validos_para_reserva(db, reserva)
    if beneficios and payload.beneficio_id is None:
        raise HTTPException(422, "Selecione um benefício para o participante")
    if payload.beneficio_id is not None and payload.beneficio_id not in beneficios:
        raise HTTPException(422, "Selecione um benefício válido para esta modalidade")
    if Decimal(str(reserva.vrtotal or 0)) == 0:
        bloquear_evento_para_cortesia(db, reserva.evento_id)
        validar_cortesia_unica_por_cpf(db, evento_id=reserva.evento_id, cpf=payload.cpf)
    beneficio = beneficios.get(payload.beneficio_id)
    participante = db.query(ReservaIngressoParticipante).filter(
        ReservaIngressoParticipante.reserva_ingresso_id == reserva_id,
        ReservaIngressoParticipante.ordem == 1,
    ).first()
    if participante is None:
        participante = ReservaIngressoParticipante(reserva_ingresso_id=reserva_id, ordem=1)
        db.add(participante)
    participante.nmparticipante = nome
    participante.cpfparticipante = payload.cpf
    participante.beneficio_id = beneficio.beneficio_id if beneficio else None
    participante.tipobeneficio = beneficio.cdbeneficio if beneficio else None
    participante.nmbeneficiosnapshot = beneficio.nmbeneficio if beneficio else None
    db.commit()
    return {"ok": True, "reserva_ingresso_id": reserva_id,
            "participante": {"nome": nome, "cpf": payload.cpf, "beneficio_id": payload.beneficio_id}}


@router.put("/{reserva_id}/participantes")
def informar_participantes(reserva_id: int, payload: ParticipantesReservaUpdate, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id).with_for_update().first()
    if not reserva:
        raise HTTPException(404, "Reserva não encontrada")
    exigir_cliente_autenticado(usuario, reserva.cliente_id)
    if reserva.sitreserva not in {"PREENCHENDO", "AGUARDANDO_PAGAMENTO"} or reserva.dtexpiracao <= datetime.now():
        reserva.sitreserva = "EXPIRADA"
        db.commit()
        raise HTTPException(409, "A reserva de ingressos expirou")
    reservas_grupo = _grupo(db, reserva)
    total_quantidade = sum(item.qtreservada for item in reservas_grupo)
    if len(payload.participantes) != total_quantidade:
        raise HTTPException(422, "Informe exatamente um participante para cada ingresso")
    cpfs = [p.cpf for p in payload.participantes]
    if len(set(cpfs)) != len(cpfs):
        raise HTTPException(422, "Cada participante deve possuir um CPF distinto")
    if Decimal(str(reserva.vrtotal or 0)) == 0:
        bloquear_evento_para_cortesia(db, reserva.evento_id)
        for cpf in cpfs:
            validar_cortesia_unica_por_cpf(
                db,
                evento_id=reserva.evento_id,
                cpf=cpf,
            )
    db.query(ReservaIngressoParticipante).filter(ReservaIngressoParticipante.reserva_ingresso_id.in_([r.reserva_ingresso_id for r in reservas_grupo])).delete(synchronize_session=False)
    posicao = 0
    for reserva_item in reservas_grupo:
        beneficios_validos = beneficios_validos_para_reserva(db, reserva_item)
        participantes_item = payload.participantes[posicao:posicao + reserva_item.qtreservada]
        if beneficios_validos and any(p.beneficio_id is None for p in participantes_item):
            raise HTTPException(422, "Selecione um benefício para cada participante")
        for participante in participantes_item:
          if participante.beneficio_id is not None and participante.beneficio_id not in beneficios_validos:
            raise HTTPException(422, "Selecione um benefício válido para esta modalidade")
          beneficio = beneficios_validos.get(participante.beneficio_id)
          ordem = participantes_item.index(participante) + 1
          db.add(ReservaIngressoParticipante(
            reserva_ingresso_id=reserva_item.reserva_ingresso_id, ordem=ordem,
            nmparticipante=participante.nome.strip(), cpfparticipante=participante.cpf,
            beneficio_id=beneficio.beneficio_id if beneficio else None,
            tipobeneficio=beneficio.cdbeneficio if beneficio else None,
            nmbeneficiosnapshot=beneficio.nmbeneficio if beneficio else None,
          ))
        posicao += reserva_item.qtreservada
    for reserva_item in reservas_grupo: reserva_item.sitreserva = "AGUARDANDO_PAGAMENTO"
    # A reserva gratuita é finalizada nesta mesma transação. Garanta que os
    # participantes recém-inseridos já possam ser consultados pelo serviço.
    db.flush()
    resultado_gratuito = None
    if float(reserva.vrtotal or 0) == 0:
        resultado_gratuito = finalizar_reserva_gratuita(db, reserva_id=reserva_id)
    db.commit()
    if resultado_gratuito and not resultado_gratuito.get("already_processed"):
        try:
            enviar_ingressos_confirmados_da_venda(db, int(resultado_gratuito["venda_id"]))
        except Exception as exc:
            # A emissão nunca pode falhar porque o e-mail está indisponível.
            print("[INGRESSO] Não foi possível enviar e-mail:", repr(exc))
    # Após o resgate gratuito as reservas passam para CONFIRMADA e deixam de
    # pertencer ao agrupamento de checkout. A resposta, porém, ainda precisa
    # devolver os itens que acabaram de ser finalizados para o app.
    itens_grupo = reservas_grupo
    resposta = _saida(db, reserva)
    resposta["itens"] = [_saida(db, item) for item in itens_grupo]
    resposta["quantidade"] = sum(item.qtreservada for item in itens_grupo)
    resposta["valor_total"] = float(sum((Decimal(str(item.vrtotal)) for item in itens_grupo), Decimal("0")))
    if getattr(reserva, "compra_evento_id", None):
        resposta["compra_evento_id"] = reserva.compra_evento_id
    return {**resposta, **(resultado_gratuito or {})}


@router.delete("/{reserva_id}")
def cancelar_reserva(reserva_id: int, cliente_id: int, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    exigir_cliente_autenticado(usuario, cliente_id)
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id, ReservaIngresso.cliente_id == cliente_id).with_for_update().first()
    if not reserva:
        raise HTTPException(404, "Reserva não encontrada")
    if reserva.sitreserva == "CONFIRMADA":
        raise HTTPException(409, "Reserva já confirmada como venda")
    _impedir_alteracao_com_pagamento(db, reserva)
    reserva.sitreserva = "CANCELADA"
    restante = []
    if getattr(reserva, "compra_evento_id", None):
        compra = db.query(CompraEvento).filter(
            CompraEvento.compra_evento_id == reserva.compra_evento_id
        ).with_for_update().first()
        if compra:
            db.query(ReservaIngresso).filter(
                ReservaIngresso.compra_evento_id == compra.compra_evento_id,
                ReservaIngresso.sitreserva != "CONFIRMADA",
            ).update({ReservaIngresso.sitreserva: "CANCELADA"}, synchronize_session=False)
            restante = db.query(ReservaIngresso).filter(
                ReservaIngresso.compra_evento_id == compra.compra_evento_id,
                ReservaIngresso.sitreserva.in_(("PREENCHENDO", "AGUARDANDO_PAGAMENTO")),
            ).all()
            compra.valor_total = sum((Decimal(str(item.vrtotal or 0)) for item in restante), Decimal("0"))
            compra.status = "ABERTA" if restante else "CANCELADA"
    db.commit()
    return {
        "ok": True,
        "status": "CANCELADA",
        "compra_evento_id": getattr(reserva, "compra_evento_id", None),
        "quantidade": sum(int(item.qtreservada or 0) for item in restante),
        "valor_total": float(sum((Decimal(str(item.vrtotal or 0)) for item in restante), Decimal("0"))),
        "itens": [_saida(db, item) for item in restante],
    }


def _reserva_para_pagamento(db: Session, reserva_id: int, cliente_id: int) -> ReservaIngresso:
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id, ReservaIngresso.cliente_id == cliente_id).with_for_update().first()
    if not reserva:
        raise HTTPException(404, "Reserva não encontrada")
    if reserva.sitreserva != "AGUARDANDO_PAGAMENTO" or reserva.dtexpiracao <= datetime.now():
        if reserva.sitreserva != "CONFIRMADA":
            reserva.sitreserva = "EXPIRADA"
        raise HTTPException(409, "A reserva não está disponível para pagamento")
    return reserva


def _cotacao_reserva(db: Session | ReservaIngresso, reserva: ReservaIngresso | str, metodo: str | None = None) -> dict:
    if metodo is None:
        metodo = str(reserva)
        reserva = db
        db = None
    itens = _grupo(db, reserva) if db is not None else [reserva]
    cotacao = cotar_itens_mercado_pago(itens, metodo)
    esperado = _valor_grupo(db, reserva) if db is not None else Decimal(str(reserva.vrtotal)).quantize(Decimal('0.01'))
    if cotacao['subtotal'] != esperado:
        raise HTTPException(409, 'Os valores da reserva divergiram. Faça uma nova reserva.')
    return cotacao


@router.post("/{reserva_id}/pix")
async def gerar_pix_reserva(reserva_id: int, payload: PagamentoReservaIn, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    # O Pix de cobrança dinâmica do Asaas pode continuar válido após a
    # reserva; não criamos novas cobranças até existir expiração segura.
    if not PIX_ASAAS_INGRESSOS_ATIVO:
        raise HTTPException(409, "Pix temporariamente indisponível para ingressos neste estabelecimento. Escolha cartão de crédito.")
    try:
        reserva = _reserva_para_pagamento(db, reserva_id, payload.cliente_id)
        valor_grupo = _valor_grupo(db, reserva)
        taxa_grupo = _taxa_grupo(db, reserva)
        referencia = f"PIX-{APP_ENV.upper()}-RESERVA-{reserva_id}-{uuid.uuid4().hex[:10]}"
        api_key_loja, wallet_loja = obter_conta_asaas_da_loja(db, reserva.loja_id)
        campanha_doacao = obter_campanha_para_reserva(db, reserva)
        campanha_doacao = validar_campanha_para_split(
            campanha_doacao, wallet_loja=wallet_loja
        )
        await garantir_webhook_pagamentos_asaas(api_key_loja)
        customer_id = await obter_ou_criar_customer_asaas_loja(db, cliente_id=reserva.cliente_id, loja_id=reserva.loja_id, api_key=api_key_loja)
        taxa_clubbar = taxa_grupo
        cobranca = await criar_cobranca_pix_asaas(customer_id=customer_id, valor=float(valor_grupo), descricao=f"Ingressos reserva {reserva_id}", external_reference=referencia, api_key=api_key_loja, splits=montar_splits_pagamento(taxa_clubbar, campanha_doacao=campanha_doacao), due_date=datetime.now().date().isoformat())
        pagamento, qr = cobranca["payment"], cobranca["qrCode"]
        payment_id = str(pagamento["id"])
        checkout = CheckoutAsaas(carrinho_id=None, reserva_ingresso_id=reserva_id, cliente_id=reserva.cliente_id, loja_id=reserva.loja_id, checkout_id=payment_id, payment_id=payment_id, pix_qr_code_id=None, pix_payload=str(qr["payload"]), pix_encoded_image=str(qr.get("encodedImage") or ""), pix_expiration_date=reserva.dtexpiracao, external_reference=referencia, status="PENDING", valor=valor_grupo, vrtaxaclubbar=taxa_clubbar, asaas_wallet_loja=wallet_loja, asaas_wallet_clubbar=ASAAS_CLUBBAR_WALLET_ID)
        db.add(checkout)
        db.flush()
        registrar_snapshot_doacao(db, checkout_asaas_id=checkout.checkout_asaas_id, campanha=campanha_doacao)
        db.commit()
        return {"reserva_ingresso_id": reserva_id, "pagamento_id": checkout.checkout_id, "pix_qr_code_id": checkout.pix_qr_code_id, "pix_copia_cola": checkout.pix_payload, "encoded_image": checkout.pix_encoded_image, "pix_expiration_date": iso_utc(checkout.pix_expiration_date), "expiration_date": iso_utc(reserva.dtexpiracao), "valor_total": float(valor_grupo), "status": "PENDENTE"}
    except HTTPException:
        db.rollback(); raise


@router.post("/{reserva_id}/checkout")
async def gerar_checkout_reserva(reserva_id: int, payload: PagamentoReservaIn, db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado)):
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    try:
        reserva = _reserva_para_pagamento(db, reserva_id, payload.cliente_id)
        valor_grupo = _valor_grupo(db, reserva)
        taxa_grupo = _taxa_grupo(db, reserva)
        cliente = db.query(Cliente).filter(Cliente.cliente_id == reserva.cliente_id).first()
        if not cliente:
            raise HTTPException(404, "Cliente não encontrado")
        validar_endereco_cobranca_para_cartao(cliente)
        segundos_restantes = int((reserva.dtexpiracao - datetime.now()).total_seconds())
        # O checkout do cartão exige ao menos dez minutos de validade. Se a
        # reserva ainda estiver ativa, estenda-a para que o cliente consiga
        # finalizar o pagamento, em vez de forçá-lo a iniciar outra compra.
        if segundos_restantes < 10 * 60:
            reserva.dtexpiracao = datetime.now() + timedelta(minutes=10)
            segundos_restantes = 10 * 60
        api_key_loja, wallet_loja = obter_conta_asaas_da_loja(db, reserva.loja_id)
        campanha_doacao = obter_campanha_para_reserva(db, reserva)
        campanha_doacao = validar_campanha_para_split(
            campanha_doacao, wallet_loja=wallet_loja
        )
        await garantir_webhook_pagamentos_asaas(api_key_loja)
        referencia = f"CLUBBAR-{APP_ENV.lower()}-RESERVA-{reserva_id}-{uuid.uuid4().hex[:10]}"
        taxa_clubbar = taxa_grupo
        permite_parcelamento = float(valor_grupo) >= 100
        resposta = await criar_checkout_asaas(valor=float(valor_grupo), descricao=f"Ingressos reserva {reserva_id}", external_reference=referencia, carrinho_id=None, reserva_ingresso_id=reserva_id, api_key=api_key_loja, splits=montar_splits_pagamento(taxa_clubbar, campanha_doacao=campanha_doacao, parcelado=permite_parcelamento, para_checkout=True), items=[{"externalReference": f"RESERVA-{reserva_id}", "name": "Ingressos Clubbar", "description": "Ingressos de modalidades selecionadas", "quantity": 1, "value": float(valor_grupo)}], billing_types=["CREDIT_CARD"], origem_checkout="CLIENT", max_installment_count=6 if permite_parcelamento else 1, minutes_to_expire=max(10, segundos_restantes // 60), nome_cliente=cliente.nmcliente, email_cliente=cliente.emailcliente, cpf_cliente=cliente.nrcpfcliente, celular_cliente=cliente.nrtelcliente, endcliente=cliente.endcliente, nrendcliente=cliente.nrendcliente, complcliente=cliente.complcliente, bairrocliente=cliente.bairrocliente, cepcliente=cliente.cepcliente)
        checkout = CheckoutAsaas(carrinho_id=None, reserva_ingresso_id=reserva_id, cliente_id=reserva.cliente_id, loja_id=reserva.loja_id, checkout_id=str(resposta["id"]), external_reference=referencia, status=str(resposta.get("status") or "ACTIVE"), checkout_url=str(resposta["link"]), valor=valor_grupo, vrtaxaclubbar=taxa_clubbar, asaas_wallet_loja=wallet_loja, asaas_wallet_clubbar=ASAAS_CLUBBAR_WALLET_ID)
        db.add(checkout)
        db.flush()
        registrar_snapshot_doacao(db, checkout_asaas_id=checkout.checkout_asaas_id, campanha=campanha_doacao)
        db.commit()
        return {"reserva_ingresso_id": reserva_id, "pagamento_id": checkout.checkout_id, "checkout_url": checkout.checkout_url, "status": checkout.status, "parcelas_solicitadas": payload.parcelas, "data_expiracao": iso_utc(reserva.dtexpiracao)}
    except HTTPException:
        db.rollback(); raise


@router.post("/{reserva_id}/cotacao-mercado-pago")
def cotar_reserva_mercado_pago(
    reserva_id: int, payload: PagamentoReservaIn, metodo: str = "PIX",
    db: Session = Depends(get_db), usuario: dict = Depends(get_usuario_logado),
):
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    reserva = _reserva_para_pagamento(db, reserva_id, payload.cliente_id)
    loja = db.query(Loja).filter(Loja.loja_id == reserva.loja_id).first()
    if not loja or str(getattr(loja, 'provedor_pagamento', 'ASAAS')).upper() != 'MERCADO_PAGO':
        raise HTTPException(409, 'Este estabelecimento não usa Mercado Pago.')
    cotacao = _cotacao_reserva(db, reserva, metodo)
    percentual = Decimal(str(reserva.pctaxa or 0))
    taxa_percentual = (Decimal(str(reserva.vrunitario)) * percentual / 100).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        **{
            chave: float(cotacao[chave]) if isinstance(cotacao[chave], Decimal) else cotacao[chave]
            for chave in ('metodo', 'ingressos', 'conveniencia', 'subtotal', 'processamento', 'total')
        },
        'percentual_conveniencia': float(percentual),
        'minimo_aplicado': Decimal(str(reserva.vrtaxa or 0)) > taxa_percentual,
    }


@router.post("/{reserva_id}/mercado-pago")
async def gerar_checkout_reserva_mercado_pago(
    reserva_id: int,
    payload: PagamentoReservaIn,
    metodo: str = "CREDIT_CARD",
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    """Cria pagamento transparente na conta Mercado Pago da loja."""
    exigir_cliente_autenticado(usuario, payload.cliente_id)
    checkout_criado_id = None
    try:
        reserva = _reserva_para_pagamento(db, reserva_id, payload.cliente_id)
        loja = db.query(Loja).filter(Loja.loja_id == reserva.loja_id).first()
        if not loja or str(getattr(loja, 'provedor_pagamento', 'ASAAS')).upper() != 'MERCADO_PAGO':
            raise HTTPException(409, 'Este estabelecimento está configurado para receber pelo Asaas.')
        metodo = metodo.upper()
        if metodo not in {'PIX', 'CREDIT_CARD', 'CREDITO'}:
            raise HTTPException(422, 'Método Mercado Pago inválido.')
        # Versões anteriores não apresentam a nova cotação. Preserve o valor
        # que elas exibiram; nunca acrescente a taxa sem confirmação do cliente.
        if payload.valor_total_confirmado is None:
            valor_cobrado = _valor_grupo(db, reserva)
            taxa_clubbar = _taxa_grupo(db, reserva)
        else:
            if metodo in {'CREDIT_CARD', 'CREDITO'} and payload.parcelas != 1:
                raise HTTPException(422, 'Para ingressos, o cartão está disponível somente à vista.')
            cotacao = _cotacao_reserva(db, reserva, metodo)
            if payload.valor_total_confirmado != cotacao['total']:
                raise HTTPException(409, 'Confirme o valor atualizado do pagamento.')
            valor_cobrado = cotacao['total']
            taxa_clubbar = cotacao['comissao_clubbar']
        cliente = db.query(Cliente).filter(
            Cliente.cliente_id == reserva.cliente_id
        ).first()
        if not cliente:
            raise HTTPException(404, 'Cliente não encontrado.')
        existente = db.query(CheckoutMercadoPago).filter(
            CheckoutMercadoPago.reserva_ingresso_id == reserva_id,
            CheckoutMercadoPago.status.in_(['CREATING', 'PENDING', 'APPROVED', 'PAID']),
        ).order_by(CheckoutMercadoPago.checkout_mercadopago_id.desc()).first()
        if existente:
            if Decimal(str(existente.valor)).quantize(Decimal('0.01')) != valor_cobrado:
                raise HTTPException(409, 'Já existe um pagamento com outro valor. Consulte a compra antes de tentar novamente.')
            if metodo == 'PIX' and existente.metodo_solicitado == 'PIX' and existente.payment_id and existente.status == 'PENDING':
                token_existente, _ = await obter_token_mercado_pago_loja(db, reserva.loja_id, lojamercadopago_id=existente.lojamercadopago_id)
                pagamento_existente = await buscar_pagamento_mp_por_id(access_token=token_existente, payment_id=existente.payment_id)
                dados_pix = (((pagamento_existente or {}).get('point_of_interaction') or {}).get('transaction_data') or {})
                if dados_pix.get('qr_code') and str(pagamento_existente.get('status') or '').lower() == 'pending':
                    return {'reserva_ingresso_id': reserva_id, 'pagamento_id': existente.preference_id,
                            'status': 'PENDING', 'pix_copia_cola': dados_pix['qr_code'],
                            'encoded_image': dados_pix.get('qr_code_base64'),
                            'pix_expiration_date': pagamento_existente.get('date_of_expiration') or iso_utc(reserva.dtexpiracao),
                            'data_expiracao': iso_utc(reserva.dtexpiracao),
                            'segundos_restantes': max(0, int((reserva.dtexpiracao - datetime.now()).total_seconds())),
                            'valor_total': float(existente.valor), 'gateway': 'MERCADO_PAGO'}
            raise HTTPException(409, 'Já existe um pagamento para esta reserva. Confira o status antes de tentar novamente.')
        if metodo in {'CREDIT_CARD', 'CREDITO'} and (not payload.card_token or not payload.payment_method_id):
            raise HTTPException(422, 'Informe os dados tokenizados do cartão.')
        if metodo == 'PIX':
            # O Mercado Pago exige 30 minutos para o Pix. Protege todo o grupo
            # até a validade do código, incluindo margem para latência da API.
            prazo_pix = datetime.now() + timedelta(minutes=31)
            for item in _grupo(db, reserva):
                item.dtexpiracao = max(item.dtexpiracao, prazo_pix)
        referencia = f'MP-{APP_ENV.upper()}-RESERVA-{reserva_id}-{uuid.uuid4().hex[:12]}'
        token, conta_mp = await obter_token_mercado_pago_loja(db, reserva.loja_id)
        checkout = CheckoutMercadoPago(
            lojamercadopago_id=conta_mp.lojamercadopago_id,
            reserva_ingresso_id=reserva_id,
            cliente_id=reserva.cliente_id,
            loja_id=reserva.loja_id,
            preference_id=referencia,
            external_reference=referencia,
            status='CREATING',
            metodo_solicitado=metodo,
            valor=valor_cobrado,
            vrtaxaclubbar=taxa_clubbar,
        )
        db.add(checkout)
        db.commit()
        checkout_criado_id = checkout.checkout_mercadopago_id
        chave = str(uuid.uuid5(uuid.NAMESPACE_URL, f'clubbar:reserva:{referencia}'))
        comum = dict(access_token=token, external_reference=referencia, titulo='INGRESSOS', nome_loja=loja.nmloja,
                     valor=valor_cobrado, valor_taxa_clubbar=taxa_clubbar,
                     chave_idempotencia=chave)
        if metodo == 'PIX':
            pagamento = await criar_pagamento_pix_mercado_pago(
                **comum, email_pagador=cliente.emailcliente,
                documento_pagador=cliente.nrcpfcliente,
            )
        else:
            pagamento = await criar_pagamento_cartao_mercado_pago(
                **comum, card_token=payload.card_token, payment_method_id=payload.payment_method_id,
                installments=payload.parcelas, issuer_id=payload.issuer_id,
                payer_email=payload.payer_email or cliente.emailcliente,
                payer_document=payload.payer_document or cliente.nrcpfcliente, device_id=payload.device_id,
            )
        if metodo == 'PIX' and pagamento.get('date_of_expiration'):
            try:
                prazo_provedor = datetime.fromisoformat(str(pagamento['date_of_expiration']).replace('Z', '+00:00'))
                if prazo_provedor.tzinfo is not None:
                    prazo_provedor = prazo_provedor.astimezone(FUSO_BRASIL).replace(tzinfo=None)
                if prazo_provedor > datetime.now():
                    for item in _grupo(db, reserva):
                        item.dtexpiracao = prazo_provedor
            except (ValueError, TypeError):
                # A margem anterior mantém o estoque reservado enquanto o
                # provedor não fornecer uma data válida.
                pass
        checkout = db.query(CheckoutMercadoPago).filter(
            CheckoutMercadoPago.checkout_mercadopago_id == checkout.checkout_mercadopago_id
        ).with_for_update().first()
        checkout.payment_id = str(pagamento['id'])
        status_mp = str(pagamento.get('status') or 'pending').upper()
        if not checkout.venda_id and checkout.status != 'REFUNDED':
            checkout.status = 'PENDING' if status_mp in {'PENDING', 'IN_PROCESS', 'APPROVED'} else status_mp
        db.commit()
        dados_pix = ((pagamento.get('point_of_interaction') or {}).get('transaction_data') or {})
        return {
            'reserva_ingresso_id': reserva_id,
            'pagamento_id': checkout.preference_id,
            'status': status_mp,
            'pix_copia_cola': dados_pix.get('qr_code'),
            'encoded_image': dados_pix.get('qr_code_base64'),
            'pix_expiration_date': pagamento.get('date_of_expiration') or iso_utc(reserva.dtexpiracao),
            'valor_total': float(checkout.valor),
            'data_expiracao': iso_utc(reserva.dtexpiracao),
            'segundos_restantes': max(0, int((reserva.dtexpiracao - datetime.now()).total_seconds())),
            'gateway': 'MERCADO_PAGO',
        }
    except HTTPException as erro:
        db.rollback()
        if checkout_criado_id and erro.status_code in {409, 422}:
            falha = db.query(CheckoutMercadoPago).filter(
                CheckoutMercadoPago.checkout_mercadopago_id == checkout_criado_id
            ).with_for_update().first()
            if falha and falha.status == 'CREATING' and not falha.payment_id:
                falha.status = 'REJECTED'
                db.commit()
        raise
    except Exception as erro:
        db.rollback()
        print('[MERCADO_PAGO RESERVA][ERRO]', repr(erro))
        raise HTTPException(500, 'Não foi possível criar o pagamento Mercado Pago.') from erro


@router.get("/{reserva_id}/status")
async def consultar_status_reserva(
    reserva_id: int,
    cliente_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    exigir_cliente_autenticado(usuario, cliente_id)
    return await status_reserva(reserva_id, cliente_id, db)


async def status_reserva(reserva_id: int, cliente_id: int, db: Session = Depends(get_db)):
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id, ReservaIngresso.cliente_id == cliente_id).first()
    if not reserva:
        raise HTTPException(404, "Reserva não encontrada")
    if reserva.venda_id:
        return {**_saida(db, reserva), "status_pagamento": "PAGO"}
    checkout_mp = db.query(CheckoutMercadoPago).filter(
        CheckoutMercadoPago.reserva_ingresso_id == reserva_id
    ).order_by(CheckoutMercadoPago.checkout_mercadopago_id.desc()).with_for_update().first()
    if checkout_mp:
        if checkout_mp.venda_id:
            return {**_saida(db, reserva), 'status_pagamento': 'PAGO'}
        if checkout_mp.status == 'REFUNDED':
            return {**_saida(db, reserva), 'status_pagamento': 'ESTORNADO'}
        if not checkout_mp.lojamercadopago_id:
            raise HTTPException(409, 'Conta original do Mercado Pago não identificada para este pagamento.')
        token, _ = await obter_token_mercado_pago_loja(
            db, checkout_mp.loja_id, lojamercadopago_id=checkout_mp.lojamercadopago_id
        )
        pagamento_mp = None
        if checkout_mp.payment_id:
            pagamento_direto = await buscar_pagamento_mp_por_id(access_token=token, payment_id=checkout_mp.payment_id)
            if pagamento_direto and str(pagamento_direto.get('status') or '').lower() == 'approved':
                pagamento_mp = pagamento_direto
            elif pagamento_direto and str(pagamento_direto.get('status') or '').lower() in {'cancelled', 'expired'}:
                checkout_mp.status = 'EXPIRED'
                db.commit()
                return {**_saida(db, reserva), 'status_pagamento': 'EXPIRED'}
        if not pagamento_mp:
            pagamento_mp = await buscar_pagamento_mercado_pago(
                access_token=token, external_reference=checkout_mp.external_reference
            )
        if pagamento_mp:
            recebido = Decimal(str(pagamento_mp.get('transaction_amount') or 0)).quantize(Decimal('0.01'))
            esperado = Decimal(str(checkout_mp.valor or 0)).quantize(Decimal('0.01'))
            if recebido != esperado:
                raise HTTPException(409, 'Valor Mercado Pago diverge da reserva.')
            resultado = await confirmar_pagamento_reserva_mp(
                db, checkout=checkout_mp, pagamento=pagamento_mp, access_token=token,
            )
            db.commit()
            if resultado.get('estornado'):
                return {**_saida(db, reserva), **resultado, 'status_pagamento': 'ESTORNADO'}
            if not resultado.get('already_processed'):
                try:
                    enviar_ingressos_confirmados_da_venda(db, int(resultado['venda_id']))
                except Exception as exc:
                    print('[INGRESSO] Não foi possível enviar e-mail:', repr(exc))
            return {**_saida(db, reserva), **resultado, 'status_pagamento': 'PAGO'}
        if reserva.dtexpiracao <= datetime.now():
            checkout_mp.status = 'EXPIRED'; reserva.sitreserva = 'EXPIRADA'; db.commit()
        return {**_saida(db, reserva), 'status_pagamento': 'PENDENTE'}
    checkout = db.query(CheckoutAsaas).filter(CheckoutAsaas.reserva_ingresso_id == reserva_id).order_by(CheckoutAsaas.checkout_asaas_id.desc()).first()
    if not checkout:
        return {**_saida(db, reserva), "status_pagamento": "PENDENTE"}
    api_key_consulta = ASAAS_API_KEY
    if checkout.asaas_wallet_loja:
        api_key_consulta, _ = obter_conta_asaas_da_loja(db, checkout.loja_id)
    pagamento = await (buscar_pagamento_confirmado_por_id(checkout.payment_id, api_key_consulta) if checkout.payment_id else buscar_pagamento_confirmado_por_qrcode_pix(checkout.pix_qr_code_id, api_key_consulta) if checkout.pix_qr_code_id else buscar_pagamento_confirmado_por_checkout(checkout.checkout_id, api_key_consulta))
    if not pagamento:
        pagamento = await buscar_pagamento_confirmado_por_referencia(checkout.external_reference, api_key_consulta)
    if pagamento:
        resultado = finalizar_reserva_paga(db, reserva_id=reserva_id, checkout_id=checkout.checkout_asaas_id, pagamento=pagamento)
        db.commit()
        if not resultado.get("already_processed"):
            try:
                enviar_ingressos_confirmados_da_venda(db, int(resultado["venda_id"]))
            except Exception as exc:
                print("[INGRESSO] Não foi possível enviar e-mail:", repr(exc))
        return {**_saida(db, reserva), **resultado, "status_pagamento": "PAGO"}
    if reserva.dtexpiracao <= datetime.now():
        if checkout.payment_id:
            await cancelar_pagamento_asaas(checkout.payment_id, api_key_consulta)
        checkout.status = "EXPIRED"
        reserva.sitreserva = "EXPIRADA"; db.commit()
    return {**_saida(db, reserva), "status_pagamento": "PENDENTE"}
