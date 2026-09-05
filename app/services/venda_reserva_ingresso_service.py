from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.checkout_asaas import CheckoutAsaas
from app.models.eventolote import EventoLote
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda
from app.models.reserva_ingresso import ReservaIngresso
from app.models.reserva_ingresso_participante import ReservaIngressoParticipante
from app.models.venda import Venda
from app.services.pagamento_status_service import set_venda_como_paga
from app.services.repasse_service import criar_repasse_da_venda
from app.services.venda_service import gerar_token_qr


def finalizar_reserva_paga(db: Session, *, reserva_id: int, checkout_id: int, pagamento: dict) -> dict:
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id).with_for_update().first()
    checkout = db.query(CheckoutAsaas).filter(CheckoutAsaas.checkout_asaas_id == checkout_id).with_for_update().first()
    if not reserva or not checkout or checkout.reserva_ingresso_id != reserva_id:
        raise HTTPException(409, "Reserva ou checkout divergente")
    if reserva.venda_id:
        return {"ok": True, "already_processed": True, "venda_id": reserva.venda_id}
    if reserva.sitreserva not in {"AGUARDANDO_PAGAMENTO", "PREENCHENDO"}:
        raise HTTPException(409, "Reserva não está aguardando pagamento")
    participantes = db.query(ReservaIngressoParticipante).filter(ReservaIngressoParticipante.reserva_ingresso_id == reserva_id).order_by(ReservaIngressoParticipante.ordem).all()
    if len(participantes) != reserva.qtreservada:
        raise HTTPException(409, "Participantes da reserva estão incompletos")
    status = str(pagamento.get("status") or "").upper()
    if status not in {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}:
        raise HTTPException(409, "Pagamento ainda não confirmado pelo Asaas")
    recebido = Decimal(str(pagamento.get("value") or 0)).quantize(Decimal("0.01"))
    esperado = Decimal(str(reserva.vrtotal)).quantize(Decimal("0.01"))
    if recebido != esperado:
        raise HTTPException(409, "Valor confirmado diverge da reserva")
    lote = db.query(EventoLote).filter(EventoLote.lote_id == reserva.lote_id).with_for_update().first()
    if not lote:
        raise HTTPException(409, "Lote da reserva não encontrado")
    venda = Venda(organizacao_id=reserva.organizacao_id, loja_id=reserva.loja_id, cliente_id=reserva.cliente_id, carrinho_id=None, reserva_ingresso_id=reserva.reserva_ingresso_id, usuario_id=None, tipovenda="INGRESSO", dsplataforma="ANDROID", sitvenda="PENDENTE", totalvenda=reserva.vrtotal)
    db.add(venda)
    db.flush()
    for participante in participantes:
        item = ItVenda(venda_id=venda.venda_id, tipoitem="INGRESSO", produto_id=None, lote_id=reserva.lote_id, qtitvenda=1, vrunititvenda=reserva.vrunitario, identregaitvenda="NAO", qrtokenitvenda=gerar_token_qr(), nmparticipante=participante.nmparticipante, cpfparticipante=participante.cpfparticipante, pctaxaitvenda=reserva.pctaxa, vrtaxaitvenda=reserva.vrtaxa, sititvenda="ATIVO")
        db.add(item)
        db.flush()
        participante.itvenda_id = item.itvenda_id
    metodo = {"PIX": "PIX", "CREDIT_CARD": "CREDITO", "DEBIT_CARD": "DEBITO"}.get(str(pagamento.get("billingType") or "").upper(), "OUTRO")
    payment_id = str(pagamento.get("id") or "")
    pag = PagVenda(venda_id=venda.venda_id, dsmetodopag=metodo, vrpagvenda=reserva.vrtotal, sitpagvenda="PENDENTE", idtransacaopagvenda=payment_id or None, provedor="ASAAS", reference_id=checkout.external_reference, checkout_id=checkout.checkout_id)
    db.add(pag)
    db.flush()
    set_venda_como_paga(db, venda_id=venda.venda_id, gateway="ASAAS", payload=pagamento, finalizar_carrinho=False)
    lote.qtvendidalote = int(lote.qtvendidalote or 0) + int(reserva.qtreservada)
    reserva.sitreserva = "CONFIRMADA"
    reserva.venda_id = venda.venda_id
    checkout.venda_id = venda.venda_id
    checkout.payment_id = payment_id or checkout.payment_id
    checkout.status = "PAID"
    checkout.dsorigemconfirmacao = "CONSULTA"
    checkout.dtconfirmacao = datetime.now()
    criar_repasse_da_venda(db, venda_id=venda.venda_id, checkout=checkout)
    return {"ok": True, "venda_id": venda.venda_id, "pagvenda_id": pag.pagvenda_id}


def finalizar_reserva_gratuita(db: Session, *, reserva_id: int) -> dict:
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id).with_for_update().first()
    if not reserva: raise HTTPException(404, "Reserva não encontrada")
    if reserva.venda_id: return {"ok": True, "already_processed": True, "venda_id": reserva.venda_id, "gratuito": True}
    if Decimal(str(reserva.vrtotal)).quantize(Decimal("0.01")) != Decimal("0.00"):
        raise HTTPException(409, "A reserva não é gratuita")
    participantes = db.query(ReservaIngressoParticipante).filter(ReservaIngressoParticipante.reserva_ingresso_id == reserva_id).order_by(ReservaIngressoParticipante.ordem).all()
    if len(participantes) != reserva.qtreservada: raise HTTPException(409, "Participantes da reserva estão incompletos")
    lote = db.query(EventoLote).filter(EventoLote.lote_id == reserva.lote_id).with_for_update().first()
    if not lote: raise HTTPException(409, "Lote da reserva não encontrado")
    venda = Venda(organizacao_id=reserva.organizacao_id, loja_id=reserva.loja_id, cliente_id=reserva.cliente_id, carrinho_id=None, reserva_ingresso_id=reserva.reserva_ingresso_id, usuario_id=None, tipovenda="INGRESSO", dsplataforma="ANDROID", sitvenda="PAGA", totalvenda=0)
    db.add(venda); db.flush()
    for participante in participantes:
        item=ItVenda(venda_id=venda.venda_id,tipoitem="INGRESSO",produto_id=None,lote_id=reserva.lote_id,qtitvenda=1,vrunititvenda=0,identregaitvenda="NAO",qrtokenitvenda=gerar_token_qr(),nmparticipante=participante.nmparticipante,cpfparticipante=participante.cpfparticipante,pctaxaitvenda=0,vrtaxaitvenda=0,sititvenda="ATIVO")
        db.add(item);db.flush();participante.itvenda_id=item.itvenda_id
    pag=PagVenda(venda_id=venda.venda_id,dsmetodopag="GRATUITO",vrpagvenda=0,sitpagvenda="PAGO",idtransacaopagvenda=f"GRATUITO-{reserva_id}",dtconftranspagvenda=datetime.now(),provedor="CLUBBAR",reference_id=f"GRATUITO-RESERVA-{reserva_id}")
    db.add(pag);db.flush()
    lote.qtvendidalote=int(lote.qtvendidalote or 0)+int(reserva.qtreservada)
    reserva.sitreserva="CONFIRMADA";reserva.venda_id=venda.venda_id
    return {"ok":True,"venda_id":venda.venda_id,"pagvenda_id":pag.pagvenda_id,"gratuito":True}
