"""Página pública, não indexável, usada nos links de ingresso enviados ao cliente."""

from html import escape

import qrcode
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from qrcode.image.svg import SvgPathImage
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.models.itvenda import ItVenda
from app.models.loja import Loja
from app.models.venda import Venda
from app.utils.datetime_utils import formatar_data_br


router = APIRouter(prefix="/publico/ingressos", tags=["Ingressos públicos"])


def _svg_qr(dados: str) -> str:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(dados)
    qr.make(fit=True)
    imagem = qr.make_image(image_factory=SvgPathImage)
    svg = imagem.to_string(encoding="unicode")
    return svg.replace("<svg ", "<svg role='img' aria-label='QR Code do ingresso' ", 1)


def _pagina_erro(mensagem: str, status_code: int) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html><html lang='pt-BR'><meta charset='utf-8'>
        <meta name='robots' content='noindex,nofollow'>
        <title>Ingresso Clubbar</title>
        <body style='margin:0;background:#f5f5f5;font-family:Arial,sans-serif;color:#222'>
        <main style='max-width:520px;margin:40px auto;padding:28px;background:#fff;border-radius:16px;text-align:center'>
        <h1 style='margin-top:0'>Clubbar</h1><p>{escape(mensagem)}</p></main></body></html>""",
        status_code=status_code,
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )


@router.get("/{token}", response_class=HTMLResponse)
def exibir_ingresso(token: str, db: Session = Depends(get_db)):
    """Mostra o QR por token opaco. Não expõe CPF, e-mail ou dados da conta."""
    if len(token) < 24:
        return _pagina_erro("Link de ingresso inválido.", 404)

    registro = (
        db.query(ItVenda, Venda, Evento, Loja, EventoLote, EventoLotePreco, EventoSetor)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .join(Loja, Loja.loja_id == Venda.loja_id)
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .join(Evento, Evento.evento_id == EventoLote.evento_id)
        .outerjoin(EventoLotePreco, EventoLotePreco.lotepreco_id == ItVenda.lotepreco_id)
        .outerjoin(EventoSetor, EventoSetor.eventosetor_id == EventoLote.eventosetor_id)
        .filter(
            ItVenda.qrtokenitvenda == token,
            ItVenda.tipoitem == "INGRESSO",
            Venda.sitvenda == "PAGA",
        )
        .first()
    )
    if not registro:
        return _pagina_erro("Ingresso não encontrado.", 404)

    item, _, evento, loja, lote, preco, setor = registro
    if item.sititvenda != "ATIVO":
        return _pagina_erro("Este ingresso foi cancelado.", 409)

    utilizado = (item.identregaitvenda or "NAO").upper() == "SIM"
    titulo = escape(evento.nmtituloevento or "Evento Clubbar")
    participante = escape(item.nmparticipante or "Participante")
    data_evento = escape(formatar_data_br(evento.dtinicioevento) or "A confirmar")
    local = escape(evento.nmlocalevento or loja.nmloja or "A confirmar")
    endereco = escape(evento.dsendlocevento or "")
    lote_texto = escape(lote.nmlote or "")
    setor_texto = escape(setor.nmsetor or "") if setor else ""
    modalidade = escape(preco.nmpreco or "") if preco else ""
    dados_qr = f"CLUBBAR-INGRESSO:{item.qrtokenitvenda}"
    bloco_qr = (
        "<div style='padding:18px;background:#fff;border-radius:14px;display:inline-block'>"
        f"{_svg_qr(dados_qr)}</div><p style='font-weight:bold;color:#167c3e'>Apresente este QR Code na entrada.</p>"
        if not utilizado
        else "<p style='padding:12px;background:#ffe7e7;color:#ad1717;border-radius:10px;font-weight:bold'>Este ingresso já foi utilizado.</p>"
    )
    detalhes = " · ".join(parte for parte in [lote_texto, setor_texto, modalidade] if parte)
    return HTMLResponse(
        f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>
        <meta name='viewport' content='width=device-width, initial-scale=1'>
        <meta name='robots' content='noindex,nofollow'><title>Ingresso Clubbar</title></head>
        <body style='margin:0;background:#f5f5f5;font-family:Arial,sans-serif;color:#202020'>
        <main style='max-width:520px;margin:0 auto;padding:20px'>
          <header style='background:#050505;color:#fff;border-radius:14px 14px 0 0;padding:20px;text-align:center;font-size:24px;font-weight:bold'>Clubbar</header>
          <section style='background:#fff;padding:28px;text-align:center;border-radius:0 0 14px 14px;box-shadow:0 2px 10px #0002'>
            <p style='margin:0 0 8px;color:#666'>Ingresso confirmado</p>
            <h1 style='font-size:24px;margin:0 0 18px'>{titulo}</h1>
            <p style='margin:6px 0'><b>Participante:</b> {participante}</p>
            <p style='margin:6px 0'><b>Data:</b> {data_evento}</p>
            <p style='margin:6px 0'><b>Local:</b> {local}</p>
            {f"<p style='margin:6px 0;color:#555'>{endereco}</p>" if endereco else ""}
            {f"<p style='margin:16px 0;color:#6840c8;font-weight:bold'>{detalhes}</p>" if detalhes else ""}
            <div style='margin-top:24px'>{bloco_qr}</div>
          </section>
        </main></body></html>""",
        headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"},
    )
