"""Notificações de ingresso disparadas somente depois da confirmação da venda."""

from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.cliente import Cliente
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventolotepreco import EventoLotePreco
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.venda import Venda
from app.services.email_service import enviar_ingressos_confirmados
from app.services.ingresso_qrcode_service import dados_qr_ingresso
from app.services.public_urls import url_api_publica
from app.utils.datetime_utils import formatar_data_br


def enviar_ingressos_confirmados_da_venda(db: Session, venda_id: int) -> bool:
    """Envia uma única mensagem com todos os ingressos recém-confirmados."""
    registros = (
        db.query(ItVenda, Cliente, Evento, Loja, EventoLote, EventoLotePreco)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Cliente, Cliente.cliente_id == Venda.cliente_id)
        .join(Loja, Loja.loja_id == Venda.loja_id)
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .outerjoin(EventoLotePreco, EventoLotePreco.lotepreco_id == ItVenda.lotepreco_id)
        .join(Evento, Evento.evento_id == EventoLote.evento_id)
        .filter(
            ItVenda.venda_id == venda_id,
            ItVenda.tipoitem == "INGRESSO",
            ItVenda.sititvenda == "ATIVO",
            Venda.sitvenda == "PAGA",
        )
        .order_by(ItVenda.itvenda_id)
        .all()
    )
    if not registros:
        return False

    primeiro_item, cliente, _, _, _ = registros[0]
    if not (cliente.emailcliente or "").strip():
        return False

    base_url = url_api_publica()
    ingressos: list[dict[str, str]] = []
    for item, _, evento, loja, _, preco in registros:
        token = (item.qrtokenitvenda or "").strip()
        if not token:
            continue
        ingressos.append(
            {
                "evento": evento.nmtituloevento or "Evento Clubbar",
                "participante": item.nmparticipante or cliente.nmcliente or "Participante",
                "data_evento": formatar_data_br(evento.dtinicioevento) or "A confirmar",
                "local": evento.nmlocalevento or loja.nmloja or "A confirmar",
                "link": f"{base_url}/publico/ingressos/{token}",
                "qr_url": f"{base_url}/publico/ingressos/{token}/qr.png",
                "dados_qr": dados_qr_ingresso(token),
                "aviso_entrada": (
                    "Válido para entrada até as "
                    f"{(evento.dtinicioevento + timedelta(minutes=int(preco.nrminutosaposinicio))).strftime('%H:%M')} horas."
                    if preco and (preco.tipopreco or "").upper() == "CORTESIA"
                    and preco.nrminutosaposinicio and evento.dtinicioevento else ""
                ),
            }
        )

    if not ingressos:
        return False
    enviar_ingressos_confirmados(
        destinatario=cliente.emailcliente.strip(),
        nome_cliente=cliente.nmcliente or "cliente",
        ingressos=ingressos,
    )
    return True
