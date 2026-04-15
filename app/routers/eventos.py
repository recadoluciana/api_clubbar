from datetime import datetime, time
from zoneinfo import ZoneInfo
import os
import uuid
import shutil
import traceback

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.loja import Loja
from app.models.evento import Evento
from app.models.cidade import Cidade
from app.models.eventolote import EventoLote
from app.schemas.evento import EventoOutBR
from app.schemas.eventolote import EventoLoteOut
from app.core.config import UPLOAD_EVENTOS

router = APIRouter(prefix="/eventos", tags=["eventos"])


def salvar_banner_evento(arquivo: UploadFile | None) -> str | None:
    if not arquivo or not arquivo.filename:
        return None

    extensao = os.path.splitext(arquivo.filename)[1].lower()
    nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
    caminho_fisico = os.path.join(UPLOAD_EVENTOS, nome_arquivo)

    with open(caminho_fisico, "wb") as buffer:
        shutil.copyfileobj(arquivo.file, buffer)

    return f"/uploads/eventos/{nome_arquivo}"


def evento_to_out_br(ev: Evento, nmloja: str | None = None, nmcidade: str | None = None):
    return {
        "evento_id": ev.evento_id,
        "organizacao_id": ev.organizacao_id,
        "loja_id": ev.loja_id,
        "nmtituloevento": ev.nmtituloevento,
        "dsdescevento": ev.dsdescevento,
        "dtinicioevento": ev.dtinicioevento,
        "dtfimevento": ev.dtfimevento,
        "nmlocalevento": ev.nmlocalevento,
        "dsendlocevento": ev.dsendlocevento,
        "urlbannerevento": ev.urlbannerevento,
        "statusevento": ev.statusevento,
        "nmloja": nmloja,
        "nmcidade": nmcidade,
    }


def hoje_inicio_br() -> datetime:
    tz = ZoneInfo("America/Sao_Paulo")
    return datetime.combine(datetime.now(tz).date(), time.min).replace(tzinfo=None)


@router.get("/lojas/{loja_id}/proximos", response_model=list[EventoOutBR])
def listar_eventos_proximos(
    loja_id: int,
    db: Session = Depends(get_db),
):
    hi = hoje_inicio_br()

    eventos = (
        db.query(Evento, Loja.nmloja, Cidade.nmcidade)
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .join(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .filter(Evento.loja_id == loja_id)
        .filter(Evento.statusevento == "ATIVO")
        .filter(Evento.dtinicioevento >= hi)
        .order_by(Evento.dtinicioevento.asc())
        .all()
    )

    return [evento_to_out_br(ev, nmloja, nmcidade) for ev, nmloja, nmcidade in eventos]


@router.get("/proximos", response_model=list[EventoOutBR])
def listar_eventos_proximos_global(
    cidade_id: int | None = None,
    db: Session = Depends(get_db),
):
    hi = hoje_inicio_br()

    q = (
        db.query(Evento, Loja.nmloja, Cidade.nmcidade)
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .join(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .filter(Evento.statusevento == "ATIVO")
        .filter(Evento.dtinicioevento >= hi)
    )

    if cidade_id:
        q = q.filter(Loja.cidade_id == cidade_id)

    eventos = q.order_by(Evento.dtinicioevento.asc()).all()

    return [evento_to_out_br(ev, nmloja, nmcidade) for ev, nmloja, nmcidade in eventos]


@router.get("/loja/{loja_id}")
def listar_eventos_da_loja(
    loja_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    eventos = (
        db.query(Evento)
        .filter(Evento.loja_id == loja_id)
        .order_by(Evento.dtinicioevento.desc())
        .all()
    )

    base_url = str(request.base_url).rstrip("/")

    return [
        {
            "evento_id": evento.evento_id,
            "organizacao_id": evento.organizacao_id,
            "loja_id": evento.loja_id,
            "nmtituloevento": evento.nmtituloevento,
            "dsdescevento": evento.dsdescevento,
            "dtinicioevento": evento.dtinicioevento,
            "dtfimevento": evento.dtfimevento,
            "nmlocalevento": evento.nmlocalevento,
            "dsendlocevento": evento.dsendlocevento,
            "urlbannerevento": f"{evento.urlbannerevento}" if evento.urlbannerevento else None,
            "statusevento": evento.statusevento,
        }
        for evento in eventos
    ]


# ROTAS MAIS ESPECÍFICAS PRIMEIRO, PARA NÃO DAR CONFLITO COM /{evento_id}
@router.get("/{evento_id}/lotes", response_model=list[EventoLoteOut])
def listar_lotes_evento(
    evento_id: int,
    db: Session = Depends(get_db),
):
    agora = datetime.now()

    lotes = (
        db.query(EventoLote)
        .filter(EventoLote.evento_id == evento_id)
        .filter(EventoLote.statuslote == "ATIVO")
        .filter(
            (EventoLote.dtiniciovenda == None)  # noqa: E711
            | (EventoLote.dtiniciovenda <= agora)
        )
        .filter(
            (EventoLote.dtfimvenda == None)  # noqa: E711
            | (EventoLote.dtfimvenda >= agora)
        )
        .order_by(EventoLote.vrprecolote.asc())
        .all()
    )

    return lotes


@router.get("/{evento_id}/lotes_todos")
def listar_todos_lotes_evento(
    evento_id: int,
    db: Session = Depends(get_db),
):
    lotes = (
        db.query(EventoLote)
        .filter(EventoLote.evento_id == evento_id)
        .order_by(EventoLote.lote_id.asc())
        .all()
    )

    return [
        {
            "lote_id": lote.lote_id,
            "organizacao_id": lote.organizacao_id,
            "loja_id": lote.loja_id,
            "evento_id": lote.evento_id,
            "nmlote": lote.nmlote,
            "vrprecolote": float(lote.vrprecolote or 0),
            "qttotallote": int(lote.qttotallote or 0),
            "qtvendidalote": int(lote.qtvendidalote or 0),
            "dtiniciovenda": lote.dtiniciovenda,
            "dtfimvenda": lote.dtfimvenda,
            "statuslote": lote.statuslote,
        }
        for lote in lotes
    ]


@router.get("/{evento_id}")
def get_evento_por_id(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    evento = (
        db.query(Evento, Loja.nmloja, Cidade.nmcidade)
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .join(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .filter(Evento.evento_id == evento_id)
        .first()
    )

    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    evento_obj, nmloja, nmcidade = evento

    lotes = (
        db.query(EventoLote)
        .filter(EventoLote.evento_id == evento_id)
        .order_by(EventoLote.lote_id.asc())
        .all()
    )

    base_url = str(request.base_url).rstrip("/")

    return {
        "evento_id": evento_obj.evento_id,
        "organizacao_id": evento_obj.organizacao_id,
        "loja_id": evento_obj.loja_id,
        "nmtituloevento": getattr(evento_obj, "nmtituloevento", None),
        "dtinicioevento": getattr(evento_obj, "dtinicioevento", None),
        "dtfimevento": getattr(evento_obj, "dtfimevento", None),
        "nmlocalevento": getattr(evento_obj, "nmlocalevento", None),
        "dsendlocevento": getattr(evento_obj, "dsendlocevento", None),
        "dsdescevento": getattr(evento_obj, "dsdescevento", None),
        "urlbannerevento": f"{evento_obj.urlbannerevento}" if getattr(evento_obj, "urlbannerevento", None) else None,
        "statusevento": getattr(evento_obj, "statusevento", None),
        "nmloja": nmloja,
        "nmcidade": nmcidade,
        "lotes": [
            {
                "lote_id": lista_lotes.lote_id,
                "nmlote": getattr(lista_lotes, "nmlote", None),
                "vrprecolote": float(getattr(lista_lotes, "vrprecolote", 0) or 0),
                "qttotallote": int(getattr(lista_lotes, "qttotallote", 0) or 0),
                "qtvendidalote": int(getattr(lista_lotes, "qtvendidalote", 0) or 0),
                "statuslote": getattr(lista_lotes, "statuslote", None),
            }
            for lista_lotes in lotes
        ],
    }


@router.post("")
def criar_evento(
    organizacao_id: int = Form(...),
    loja_id: int = Form(...),
    nmtituloevento: str = Form(...),
    dsdescevento: str | None = Form(None),
    dtinicioevento: str = Form(...),
    dtfimevento: str | None = Form(None),
    nmlocalevento: str | None = Form(None),
    dsendlocevento: str | None = Form(None),
    statusevento: str = Form("RASCUNHO"),
    urlbannerevento: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    try:
        loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
        if not loja:
            raise HTTPException(status_code=404, detail="Loja não encontrada")

        banner_url = salvar_banner_evento(urlbannerevento)

        novo = Evento(
            organizacao_id=organizacao_id,
            loja_id=loja_id,
            nmtituloevento=nmtituloevento,
            dsdescevento=dsdescevento,
            dtinicioevento=datetime.fromisoformat(dtinicioevento),
            dtfimevento=datetime.fromisoformat(dtfimevento) if dtfimevento else None,
            nmlocalevento=nmlocalevento,
            dsendlocevento=dsendlocevento,
            urlbannerevento=banner_url,
            statusevento=statusevento,
        )

        db.add(novo)
        db.commit()
        db.refresh(novo)

        return {
            "mensagem": "Evento cadastrado com sucesso",
            "evento_id": novo.evento_id,
            "urlbannerevento": novo.urlbannerevento,
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao criar evento: {str(e)}")


@router.put("/{evento_id}")
def atualizar_evento(
    evento_id: int,
    organizacao_id: int | None = Form(None),
    loja_id: int | None = Form(None),
    nmtituloevento: str | None = Form(None),
    dsdescevento: str | None = Form(None),
    dtinicioevento: str | None = Form(None),
    dtfimevento: str | None = Form(None),
    nmlocalevento: str | None = Form(None),
    dsendlocevento: str | None = Form(None),
    statusevento: str | None = Form(None),
    urlbannerevento: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    try:
        evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()

        if not evento:
            raise HTTPException(status_code=404, detail="Evento não encontrado")

        if organizacao_id is not None:
            evento.organizacao_id = organizacao_id

        if loja_id is not None:
            loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
            if not loja:
                raise HTTPException(status_code=404, detail="Loja não encontrada")
            evento.loja_id = loja_id

        if nmtituloevento is not None:
            evento.nmtituloevento = nmtituloevento

        if dsdescevento is not None:
            evento.dsdescevento = dsdescevento

        if dtinicioevento is not None:
            evento.dtinicioevento = datetime.fromisoformat(dtinicioevento)

        if dtfimevento is not None:
            evento.dtfimevento = datetime.fromisoformat(dtfimevento) if dtfimevento else None

        if nmlocalevento is not None:
            evento.nmlocalevento = nmlocalevento

        if dsendlocevento is not None:
            evento.dsendlocevento = dsendlocevento

        if statusevento is not None:
            evento.statusevento = statusevento

        if urlbannerevento is not None and urlbannerevento.filename:
            evento.urlbannerevento = salvar_banner_evento(urlbannerevento)

        db.commit()
        db.refresh(evento)

        return {
            "mensagem": "Evento atualizado com sucesso",
            "evento": {
                "evento_id": evento.evento_id,
                "organizacao_id": evento.organizacao_id,
                "loja_id": evento.loja_id,
                "nmtituloevento": evento.nmtituloevento,
                "dsdescevento": evento.dsdescevento,
                "dtinicioevento": evento.dtinicioevento,
                "dtfimevento": evento.dtfimevento,
                "nmlocalevento": evento.nmlocalevento,
                "dsendlocevento": evento.dsendlocevento,
                "urlbannerevento": evento.urlbannerevento,
                "statusevento": evento.statusevento,
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao atualizar evento: {str(e)}")


@router.delete("/{evento_id}")
def deletar_evento(evento_id: int, db: Session = Depends(get_db)):
    try:
        evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()

        if not evento:
            raise HTTPException(status_code=404, detail="Evento não encontrado")

        db.delete(evento)
        db.commit()

        return {"mensagem": "Evento deletado com sucesso"}

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar evento: {str(e)}")

