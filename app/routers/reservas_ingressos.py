from datetime import datetime, timedelta
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.reserva_ingresso import ReservaIngresso
from app.models.reserva_ingresso_participante import ReservaIngressoParticipante
from app.models.checkout_asaas import CheckoutAsaas
from app.models.cliente import Cliente
from app.schemas.reserva_ingresso import ReservaIngressoCreate, ParticipantesReservaUpdate, PagamentoReservaIn
from app.services.reserva_ingresso_service import criar_reserva
from app.services.asaas_service import criar_checkout_asaas, criar_qrcode_pix_estatico_asaas, buscar_pagamento_confirmado_por_checkout, buscar_pagamento_confirmado_por_qrcode_pix, buscar_pagamento_confirmado_por_referencia
from app.services.venda_reserva_ingresso_service import finalizar_reserva_paga, finalizar_reserva_gratuita
from app.core.config import APP_ENV, ASAAS_API_KEY, ASAAS_PIX_ADDRESS_KEY, ASAAS_CLUBBAR_WALLET_ID
from app.services.asaas_split_service import obter_conta_asaas_da_loja, montar_split_clubbar
from app.utils.datetime_utils import iso_utc

router = APIRouter(prefix="/reservas-ingressos", tags=["Reservas de ingressos"])


def _saida(reserva: ReservaIngresso) -> dict:
    return {
        "reserva_ingresso_id": reserva.reserva_ingresso_id,
        "organizacao_id": reserva.organizacao_id,
        "loja_id": reserva.loja_id,
        "cliente_id": reserva.cliente_id,
        "evento_id": reserva.evento_id,
        "lote_id": reserva.lote_id,
        "quantidade": reserva.qtreservada,
        "valor_unitario": float(reserva.vrunitario),
        "percentual_taxa": float(reserva.pctaxa),
        "valor_taxa_unitaria": float(reserva.vrtaxa),
        "valor_total": float(reserva.vrtotal),
        "status": reserva.sitreserva,
        "data_expiracao": iso_utc(reserva.dtexpiracao),
        "venda_id": reserva.venda_id,
    }


@router.post("")
def reservar(payload: ReservaIngressoCreate, db: Session = Depends(get_db)):
    try:
        reserva = criar_reserva(db, cliente_id=payload.cliente_id, lote_id=payload.lote_id, quantidade=payload.quantidade)
        db.commit()
        db.refresh(reserva)
        return _saida(reserva)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise


@router.put("/{reserva_id}/participantes")
def informar_participantes(reserva_id: int, payload: ParticipantesReservaUpdate, db: Session = Depends(get_db)):
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id).with_for_update().first()
    if not reserva:
        raise HTTPException(404, "Reserva não encontrada")
    if reserva.sitreserva not in {"PREENCHENDO", "AGUARDANDO_PAGAMENTO"} or reserva.dtexpiracao <= datetime.now():
        reserva.sitreserva = "EXPIRADA"
        db.commit()
        raise HTTPException(409, "A reserva de ingressos expirou")
    if len(payload.participantes) != reserva.qtreservada:
        raise HTTPException(422, "Informe exatamente um participante para cada ingresso")
    cpfs = [p.cpf for p in payload.participantes]
    if len(set(cpfs)) != len(cpfs):
        raise HTTPException(422, "Cada participante deve possuir um CPF distinto")
    db.query(ReservaIngressoParticipante).filter(ReservaIngressoParticipante.reserva_ingresso_id == reserva_id).delete()
    for ordem, participante in enumerate(payload.participantes, 1):
        db.add(ReservaIngressoParticipante(reserva_ingresso_id=reserva_id, ordem=ordem, nmparticipante=participante.nome.strip(), cpfparticipante=participante.cpf))
    reserva.sitreserva = "AGUARDANDO_PAGAMENTO"
    reserva.dtexpiracao = datetime.now() + timedelta(minutes=5)
    # A reserva gratuita é finalizada nesta mesma transação. Garanta que os
    # participantes recém-inseridos já possam ser consultados pelo serviço.
    db.flush()
    resultado_gratuito = None
    if float(reserva.vrtotal or 0) == 0:
        resultado_gratuito = finalizar_reserva_gratuita(db, reserva_id=reserva_id)
    db.commit()
    return {**_saida(reserva), **(resultado_gratuito or {})}


@router.delete("/{reserva_id}")
def cancelar_reserva(reserva_id: int, cliente_id: int, db: Session = Depends(get_db)):
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id, ReservaIngresso.cliente_id == cliente_id).with_for_update().first()
    if not reserva:
        raise HTTPException(404, "Reserva não encontrada")
    if reserva.sitreserva == "CONFIRMADA":
        raise HTTPException(409, "Reserva já confirmada como venda")
    reserva.sitreserva = "CANCELADA"
    db.commit()
    return {"ok": True, "status": "CANCELADA"}


def _reserva_para_pagamento(db: Session, reserva_id: int, cliente_id: int) -> ReservaIngresso:
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id, ReservaIngresso.cliente_id == cliente_id).with_for_update().first()
    if not reserva:
        raise HTTPException(404, "Reserva não encontrada")
    if reserva.sitreserva != "AGUARDANDO_PAGAMENTO" or reserva.dtexpiracao <= datetime.now():
        if reserva.sitreserva != "CONFIRMADA":
            reserva.sitreserva = "EXPIRADA"
        raise HTTPException(409, "A reserva não está disponível para pagamento")
    return reserva


@router.post("/{reserva_id}/pix")
async def gerar_pix_reserva(reserva_id: int, payload: PagamentoReservaIn, db: Session = Depends(get_db)):
    try:
        reserva = _reserva_para_pagamento(db, reserva_id, payload.cliente_id)
        referencia = f"PIX-{APP_ENV.upper()}-RESERVA-{reserva_id}-{uuid.uuid4().hex[:10]}"
        qr = await criar_qrcode_pix_estatico_asaas(address_key=ASAAS_PIX_ADDRESS_KEY, valor=float(reserva.vrtotal), descricao=f"Ingressos reserva {reserva_id}", api_key=ASAAS_API_KEY, external_reference=referencia, expiracao_segundos=300)
        checkout = CheckoutAsaas(carrinho_id=None, reserva_ingresso_id=reserva_id, cliente_id=reserva.cliente_id, loja_id=reserva.loja_id, checkout_id=str(qr["id"]), pix_qr_code_id=str(qr["id"]), pix_payload=str(qr["payload"]), pix_encoded_image=str(qr.get("encodedImage") or ""), pix_expiration_date=datetime.now() + timedelta(minutes=5), external_reference=referencia, status="PENDING", valor=reserva.vrtotal, vrtaxaclubbar=reserva.vrtaxa * reserva.qtreservada)
        db.add(checkout)
        reserva.dtexpiracao = datetime.now() + timedelta(minutes=5)
        db.commit()
        return {"reserva_ingresso_id": reserva_id, "pagamento_id": checkout.checkout_id, "pix_qr_code_id": checkout.pix_qr_code_id, "pix_copia_cola": checkout.pix_payload, "encoded_image": checkout.pix_encoded_image, "pix_expiration_date": iso_utc(checkout.pix_expiration_date), "valor_total": float(reserva.vrtotal), "status": "PENDENTE"}
    except HTTPException:
        db.rollback(); raise


@router.post("/{reserva_id}/checkout")
async def gerar_checkout_reserva(reserva_id: int, payload: PagamentoReservaIn, db: Session = Depends(get_db)):
    try:
        reserva = _reserva_para_pagamento(db, reserva_id, payload.cliente_id)
        cliente = db.query(Cliente).filter(Cliente.cliente_id == reserva.cliente_id).first()
        api_key_loja, wallet_loja = obter_conta_asaas_da_loja(db, reserva.loja_id)
        referencia = f"CLUBBAR-{APP_ENV.lower()}-RESERVA-{reserva_id}-{uuid.uuid4().hex[:10]}"
        taxa_clubbar = reserva.vrtaxa * reserva.qtreservada
        permite_parcelamento = float(reserva.vrtotal) >= 100
        resposta = await criar_checkout_asaas(valor=float(reserva.vrtotal), descricao=f"Ingressos reserva {reserva_id}", external_reference=referencia, carrinho_id=None, reserva_ingresso_id=reserva_id, api_key=api_key_loja, splits=montar_split_clubbar(taxa_clubbar, parcelado=permite_parcelamento), items=[{"externalReference": f"LOTE-{reserva.lote_id}", "name": "Ingresso Clubbar", "description": f"{reserva.qtreservada} ingresso(s)", "quantity": reserva.qtreservada, "value": float(reserva.vrunitario + reserva.vrtaxa)}], billing_types=["CREDIT_CARD"], origem_checkout="CLIENT", max_installment_count=6 if permite_parcelamento else 1, nome_cliente=cliente.nmcliente, email_cliente=cliente.emailcliente, cpf_cliente=cliente.nrcpfcliente, celular_cliente=cliente.nrtelcliente, endcliente=cliente.endcliente, nrendcliente=cliente.nrendcliente, complcliente=cliente.complcliente, bairrocliente=cliente.bairrocliente, cepcliente=cliente.cepcliente)
        checkout = CheckoutAsaas(carrinho_id=None, reserva_ingresso_id=reserva_id, cliente_id=reserva.cliente_id, loja_id=reserva.loja_id, checkout_id=str(resposta["id"]), external_reference=referencia, status=str(resposta.get("status") or "ACTIVE"), checkout_url=str(resposta["link"]), valor=reserva.vrtotal, vrtaxaclubbar=taxa_clubbar, asaas_wallet_loja=wallet_loja, asaas_wallet_clubbar=ASAAS_CLUBBAR_WALLET_ID)
        db.add(checkout)
        reserva.dtexpiracao = datetime.now() + timedelta(minutes=10)
        db.commit()
        return {"reserva_ingresso_id": reserva_id, "pagamento_id": checkout.checkout_id, "checkout_url": checkout.checkout_url, "status": checkout.status, "parcelas_solicitadas": payload.parcelas}
    except HTTPException:
        db.rollback(); raise


@router.get("/{reserva_id}/status")
async def status_reserva(reserva_id: int, cliente_id: int, db: Session = Depends(get_db)):
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id, ReservaIngresso.cliente_id == cliente_id).first()
    if not reserva:
        raise HTTPException(404, "Reserva não encontrada")
    if reserva.venda_id:
        return {**_saida(reserva), "status_pagamento": "PAGO"}
    checkout = db.query(CheckoutAsaas).filter(CheckoutAsaas.reserva_ingresso_id == reserva_id).order_by(CheckoutAsaas.checkout_asaas_id.desc()).first()
    if not checkout:
        return {**_saida(reserva), "status_pagamento": "PENDENTE"}
    api_key_consulta = ASAAS_API_KEY
    if checkout.asaas_wallet_loja:
        api_key_consulta, _ = obter_conta_asaas_da_loja(db, checkout.loja_id)
    pagamento = await (buscar_pagamento_confirmado_por_qrcode_pix(checkout.pix_qr_code_id, api_key_consulta) if checkout.pix_qr_code_id else buscar_pagamento_confirmado_por_checkout(checkout.checkout_id, api_key_consulta))
    if not pagamento:
        pagamento = await buscar_pagamento_confirmado_por_referencia(checkout.external_reference, api_key_consulta)
    if pagamento:
        resultado = finalizar_reserva_paga(db, reserva_id=reserva_id, checkout_id=checkout.checkout_asaas_id, pagamento=pagamento)
        db.commit()
        return {**_saida(reserva), **resultado, "status_pagamento": "PAGO"}
    if reserva.dtexpiracao <= datetime.now():
        reserva.sitreserva = "EXPIRADA"; db.commit()
    return {**_saida(reserva), "status_pagamento": "PENDENTE"}
