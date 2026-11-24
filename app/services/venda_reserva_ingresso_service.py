from datetime import datetime
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.checkout_asaas import CheckoutAsaas
from app.models.eventolote import EventoLote
from app.models.eventolotepreco import EventoLotePreco
from app.models.itvenda import ItVenda
from app.models.pagvenda import PagVenda
from app.models.reserva_ingresso import ReservaIngresso
from app.models.reserva_ingresso_participante import ReservaIngressoParticipante
from app.models.compra_evento import CompraEvento
from app.models.venda import Venda
from app.services.pagamento_status_service import set_venda_como_paga
from app.services.venda_service import gerar_token_qr
from app.services.taxa_processamento_ingresso import distribuir_processamento
from app.services.cortesia_evento_service import bloquear_evento_para_cortesia, validar_cortesia_unica_por_cpf


def _dados_catalogo_item(
    db: Session,
    reserva: ReservaIngresso,
    participante: ReservaIngressoParticipante | None = None,
) -> dict:
    preco = db.query(EventoLotePreco).filter(EventoLotePreco.lotepreco_id == reserva.lotepreco_id).first()
    return {
        "modalidade_id": preco.modalidade_id if preco else None,
        "beneficio_id": participante.beneficio_id if participante and participante.beneficio_id is not None else reserva.beneficio_id,
        "tipobeneficio": participante.tipobeneficio if participante and participante.tipobeneficio is not None else reserva.tipobeneficio,
        "nmmodalidadesnapshot": preco.nmpreco if preco else None,
        "nmbeneficiosnapshot": participante.nmbeneficiosnapshot if participante and participante.nmbeneficiosnapshot is not None else reserva.nmbeneficiosnapshot,
    }


def finalizar_reserva_paga(
    db: Session,
    *,
    reserva_id: int,
    checkout_id: int,
    pagamento: dict,
    gateway: str = "ASAAS",
    modelo_checkout=CheckoutAsaas,
) -> dict:
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id).with_for_update().first()
    chave_checkout = (
        modelo_checkout.checkout_asaas_id
        if gateway.upper() == "ASAAS"
        else modelo_checkout.checkout_mercadopago_id
    )
    checkout = db.query(modelo_checkout).filter(chave_checkout == checkout_id).with_for_update().first()
    if not reserva or not checkout or checkout.reserva_ingresso_id != reserva_id:
        raise HTTPException(409, "Reserva ou checkout divergente")
    if reserva.venda_id:
        return {"ok": True, "already_processed": True, "venda_id": reserva.venda_id}
    if reserva.sitreserva not in {"AGUARDANDO_PAGAMENTO", "PREENCHENDO"}:
        raise HTTPException(409, "Reserva não está aguardando pagamento")
    grupo_id = getattr(reserva, "grupo_reserva_id", None)
    grupo = db.query(ReservaIngresso).filter(
        ReservaIngresso.grupo_reserva_id == grupo_id
    ).with_for_update().all() if grupo_id else [reserva]
    ids_grupo = [item.reserva_ingresso_id for item in grupo]
    participantes = db.query(ReservaIngressoParticipante).filter(
        ReservaIngressoParticipante.reserva_ingresso_id.in_(ids_grupo)
    ).order_by(ReservaIngressoParticipante.reserva_ingresso_id, ReservaIngressoParticipante.ordem).all()
    if len(participantes) != sum(item.qtreservada for item in grupo):
        raise HTTPException(409, "Participantes da reserva estão incompletos")
    status = str(pagamento.get("status") or "").upper()
    confirmados = {"RECEIVED", "CONFIRMED", "RECEIVED_IN_CASH"}
    if gateway.upper() == "MERCADO_PAGO":
        confirmados = {"APPROVED"}
    if status not in confirmados:
        raise HTTPException(409, f"Pagamento ainda não confirmado pelo {gateway.title()}")
    recebido = Decimal(str(
        pagamento.get("value") if gateway.upper() == "ASAAS"
        else pagamento.get("transaction_amount")
    )).quantize(Decimal("0.01"))
    valor_reserva = sum((Decimal(str(item.vrtotal)) for item in grupo), Decimal("0")).quantize(Decimal("0.01"))
    esperado = Decimal(str(checkout.valor)).quantize(Decimal("0.01")) if gateway.upper() == "MERCADO_PAGO" else valor_reserva
    # Rateie o processamento por ingresso para que a soma dos itens e os
    # reembolsos reflitam o valor efetivamente cobrado. A comissão do Clubbar
    # continua registrada separadamente no checkout, sem incluir essa parcela.
    adicional = esperado - valor_reserva
    parcelas_processamento = distribuir_processamento(adicional, len(participantes))
    if recebido != esperado:
        raise HTTPException(409, "Valor confirmado diverge da reserva")
    lotes = {item.lote_id: db.query(EventoLote).filter(EventoLote.lote_id == item.lote_id).with_for_update().first() for item in grupo}
    if any(not lote for lote in lotes.values()): raise HTTPException(409, "Lote da reserva não encontrado")
    venda = Venda(organizacao_id=reserva.organizacao_id, loja_id=reserva.loja_id, cliente_id=reserva.cliente_id, carrinho_id=None, reserva_ingresso_id=reserva.reserva_ingresso_id, usuario_id=None, tipovenda="INGRESSO", dsplataforma="ANDROID", sitvenda="PENDENTE", totalvenda=esperado)
    db.add(venda)
    db.flush()
    indice = 0
    for reserva_item in grupo:
      itens_reserva = [p for p in participantes if getattr(p, 'reserva_ingresso_id', reserva_item.reserva_ingresso_id) == reserva_item.reserva_ingresso_id]
      for participante in itens_reserva:
        item = ItVenda(venda_id=venda.venda_id, tipoitem="INGRESSO", produto_id=None, lote_id=reserva_item.lote_id, lotepreco_id=reserva_item.lotepreco_id, qtitvenda=1, vrunititvenda=reserva_item.vrunitario, identregaitvenda="NAO", qrtokenitvenda=gerar_token_qr(), nmparticipante=participante.nmparticipante, cpfparticipante=participante.cpfparticipante, pctaxaitvenda=reserva_item.pctaxa, vrtaxaitvenda=Decimal(str(reserva_item.vrtaxa or 0)) + parcelas_processamento[indice], sititvenda="ATIVO", **_dados_catalogo_item(db, reserva_item, participante))
        indice += 1
        db.add(item)
        db.flush()
        participante.itvenda_id = item.itvenda_id
    metodo = {"PIX": "PIX", "CREDIT_CARD": "CREDITO", "DEBIT_CARD": "DEBITO"}.get(str(pagamento.get("billingType") or "").upper(), "OUTRO")
    if gateway.upper() == "MERCADO_PAGO":
        metodo = {
            "credit_card": "CREDITO", "debit_card": "DEBITO", "pix": "PIX",
            "bank_transfer": "PIX",
        }.get(str(pagamento.get("payment_type_id") or pagamento.get("payment_method_id") or "").lower(), "OUTRO")
    payment_id = str(pagamento.get("id") or "")
    checkout_referencia = (
        checkout.checkout_id if gateway.upper() == "ASAAS" else checkout.preference_id
    )
    pag = PagVenda(venda_id=venda.venda_id, dsmetodopag=metodo, vrpagvenda=esperado, sitpagvenda="PENDENTE", idtransacaopagvenda=payment_id or None, provedor=gateway.upper(), reference_id=checkout.external_reference, checkout_id=checkout_referencia, lojamercadopago_id=getattr(checkout, 'lojamercadopago_id', None) if gateway.upper() == 'MERCADO_PAGO' else None)
    db.add(pag)
    db.flush()
    set_venda_como_paga(db, venda_id=venda.venda_id, gateway=gateway.upper(), payload=pagamento, finalizar_carrinho=False)
    for reserva_item in grupo:
        lotes[reserva_item.lote_id].qtvendidalote = int(lotes[reserva_item.lote_id].qtvendidalote or 0) + int(reserva_item.qtreservada)
    # Após a confirmação, o total da reserva deve refletir o valor pago.
    for reserva_item in grupo:
        reserva_item.vrtotal = esperado if len(grupo) == 1 else reserva_item.vrtotal
        reserva_item.sitreserva = "CONFIRMADA"
        reserva_item.venda_id = venda.venda_id
    if getattr(reserva, "compra_evento_id", None):
        compra = db.query(CompraEvento).filter(
            CompraEvento.compra_evento_id == reserva.compra_evento_id
        ).with_for_update().first()
        if compra:
            compra.status = "PAGA"
            compra.venda_id = venda.venda_id
            compra.valor_total = esperado
    checkout.venda_id = venda.venda_id
    checkout.payment_id = payment_id or checkout.payment_id
    checkout.status = "PAID"
    checkout.dsorigemconfirmacao = "CONSULTA"
    checkout.dtconfirmacao = datetime.now()
    return {"ok": True, "venda_id": venda.venda_id, "pagvenda_id": pag.pagvenda_id}


def finalizar_reserva_gratuita(db: Session, *, reserva_id: int) -> dict:
    # Este serviço também pode ser chamado logo após a inclusão dos
    # participantes, antes do commit da transação externa.
    db.flush()
    reserva = db.query(ReservaIngresso).filter(ReservaIngresso.reserva_ingresso_id == reserva_id).with_for_update().first()
    if not reserva: raise HTTPException(404, "Reserva não encontrada")
    if reserva.venda_id: return {"ok": True, "already_processed": True, "venda_id": reserva.venda_id, "gratuito": True}
    grupo = _grupo(db, reserva)
    if any(Decimal(str(item.vrtotal)).quantize(Decimal("0.01")) != Decimal("0.00") for item in grupo):
        raise HTTPException(409, "A reserva não é gratuita")
    ids_grupo = [item.reserva_ingresso_id for item in grupo]
    participantes = db.query(ReservaIngressoParticipante).filter(
        ReservaIngressoParticipante.reserva_ingresso_id.in_(ids_grupo)
    ).order_by(
        ReservaIngressoParticipante.reserva_ingresso_id,
        ReservaIngressoParticipante.ordem,
    ).all()
    if len(participantes) != sum(item.qtreservada for item in grupo):
        raise HTTPException(409, "Participantes da reserva estão incompletos")
    bloquear_evento_para_cortesia(db, reserva.evento_id)
    for participante in participantes:
        validar_cortesia_unica_por_cpf(
            db,
            evento_id=reserva.evento_id,
            cpf=participante.cpfparticipante,
        )
    lotes = {
        item.lote_id: db.query(EventoLote).filter(
            EventoLote.lote_id == item.lote_id
        ).with_for_update().first()
        for item in grupo
    }
    if any(lote is None for lote in lotes.values()):
        raise HTTPException(409, "Lote da reserva não encontrado")
    venda = Venda(organizacao_id=reserva.organizacao_id, loja_id=reserva.loja_id, cliente_id=reserva.cliente_id, carrinho_id=None, reserva_ingresso_id=reserva.reserva_ingresso_id, usuario_id=None, tipovenda="INGRESSO", dsplataforma="ANDROID", sitvenda="PAGA", totalvenda=0)
    db.add(venda); db.flush()
    por_reserva = {}
    for participante in participantes:
        por_reserva.setdefault(participante.reserva_ingresso_id, []).append(participante)
    for reserva_item in grupo:
        for participante in por_reserva.get(reserva_item.reserva_ingresso_id, []):
            item=ItVenda(venda_id=venda.venda_id,tipoitem="INGRESSO",produto_id=None,lote_id=reserva_item.lote_id,lotepreco_id=reserva_item.lotepreco_id,qtitvenda=1,vrunititvenda=0,identregaitvenda="NAO",qrtokenitvenda=gerar_token_qr(),nmparticipante=participante.nmparticipante,cpfparticipante=participante.cpfparticipante,pctaxaitvenda=0,vrtaxaitvenda=0,sititvenda="ATIVO",**_dados_catalogo_item(db, reserva_item, participante))
            db.add(item);db.flush();participante.itvenda_id=item.itvenda_id
    pag=PagVenda(venda_id=venda.venda_id,dsmetodopag="GRATUITO",vrpagvenda=0,sitpagvenda="PAGO",idtransacaopagvenda=f"GRATUITO-{reserva_id}",dtconftranspagvenda=datetime.now(),provedor="CLUBBAR",reference_id=f"GRATUITO-RESERVA-{reserva_id}")
    db.add(pag);db.flush()
    for reserva_item in grupo:
        lote = lotes[reserva_item.lote_id]
        lote.qtvendidalote=int(lote.qtvendidalote or 0)+int(reserva_item.qtreservada)
        reserva_item.sitreserva="CONFIRMADA";reserva_item.venda_id=venda.venda_id
    return {"ok":True,"venda_id":venda.venda_id,"pagvenda_id":pag.pagvenda_id,"gratuito":True}
