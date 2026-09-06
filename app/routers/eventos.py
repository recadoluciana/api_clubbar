from datetime import datetime, time
from zoneinfo import ZoneInfo
import os
import uuid
import shutil
import traceback

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_usuario_logado
from app.services.onboarding_parceiro_service import validar_publicacao_loja
from app.core.permissoes_loja import validar_mutacao_loja
from app.models.loja import Loja
from app.models.evento import Evento
from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.eventolote import EventoLote
from app.models.eventoatracao import EventoAtracao
from app.models.atracao import Atracao
from app.models.organizacao import Organizacao
from app.models.venda import Venda
from app.schemas.evento import EventoOutBR
from app.core.config import UPLOAD_EVENTOS

router = APIRouter(prefix="/eventos", tags=["eventos"])


def salvar_banner_evento(arquivo: UploadFile | None) -> str | None:
    if not arquivo or not arquivo.filename:
        return None

    extensao = os.path.splitext(arquivo.filename)[1].lower()
    nome_arquivo = f"{uuid.uuid4().hex}{extensao}"
    caminho_fisico = UPLOAD_EVENTOS / nome_arquivo

    with open(caminho_fisico, "wb") as buffer:
        shutil.copyfileobj(arquivo.file, buffer)

    return f"/uploads/eventos/{nome_arquivo}"


def evento_to_out_br(
    ev: Evento,
    nmloja: str | None = None,
    nmcidade: str | None = None,
    urllogoloja: str | None = None,
    total_vendas_loja: int = 0,
):
    return {
        "evento_id": ev.evento_id,
        "organizacao_id": ev.organizacao_id,
        "loja_id": ev.loja_id,
        "nmtituloevento": ev.nmtituloevento,
        "dsdescevento": ev.dsdescevento,
        "dspoliticacancelamento": ev.dspoliticacancelamento,
        "dspoliticareembolso": ev.dspoliticareembolso,
        "dspoliticacashback": ev.dspoliticacashback,
        "dtinicioevento": ev.dtinicioevento,
        "dtfimevento": ev.dtfimevento,
        "nmlocalevento": ev.nmlocalevento,
        "dsendlocevento": ev.dsendlocevento,
        "urlbannerevento": ev.urlbannerevento,
        "statusevento": ev.statusevento,
        "nmloja": nmloja,
        "nmcidade": nmcidade,
        "urllogoloja": urllogoloja,
        "total_vendas_loja": total_vendas_loja,
    }


def hoje_inicio_br() -> datetime:
    tz = ZoneInfo("America/Sao_Paulo")
    return datetime.combine(datetime.now(tz).date(), time.min).replace(tzinfo=None)


def filtro_evento_atual_ou_proximo(inicio_dia: datetime):
    """Inclui eventos que começam hoje/no futuro ou que ainda não terminaram."""
    return or_(
        Evento.dtinicioevento >= inicio_dia,
        Evento.dtfimevento >= inicio_dia,
    )


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
        .join(Organizacao, Organizacao.organizacao_id == Evento.organizacao_id)
        .filter(Organizacao.sitorganizacao == "ATIVA")
        .filter(Evento.loja_id == loja_id)
        .filter(Evento.statusevento == "ATIVO")
        .filter(filtro_evento_atual_ou_proximo(hi))
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

    vendas_por_loja = (
        db.query(
            Venda.loja_id.label("loja_id"),
            func.count(Venda.venda_id).label("total_vendas"),
        )
        .filter(Venda.sitvenda == "PAGA")
        .group_by(Venda.loja_id)
        .subquery()
    )

    q = (
        db.query(
            Evento,
            Loja.nmloja,
            Cidade.nmcidade,
            Loja.urllogoloja,
            func.coalesce(vendas_por_loja.c.total_vendas, 0).label("total_vendas_loja"),
        )
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .join(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .outerjoin(vendas_por_loja, vendas_por_loja.c.loja_id == Loja.loja_id)
        .join(
            Organizacao,
            Organizacao.organizacao_id == Evento.organizacao_id,
        )
        .filter(Organizacao.sitorganizacao == "ATIVA")
        .filter(Evento.statusevento == "ATIVO")
        .filter(filtro_evento_atual_ou_proximo(hi))
    )

    if cidade_id:
        q = q.filter(Loja.cidade_id == cidade_id)

    eventos = (
        q.order_by(
            func.coalesce(vendas_por_loja.c.total_vendas, 0).desc(),
            Evento.dtinicioevento.asc(),
            Evento.evento_id.asc(),
        )
        .limit(10)
        .all()
    )

    return [
        evento_to_out_br(ev, nmloja, nmcidade, urllogoloja, total_vendas_loja)
        for ev, nmloja, nmcidade, urllogoloja, total_vendas_loja in eventos
    ]


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
            "dspoliticacancelamento": evento.dspoliticacancelamento,
            "dspoliticareembolso": evento.dspoliticareembolso,
            "dspoliticacashback": evento.dspoliticacashback,
            "dtinicioevento": evento.dtinicioevento,
            "dtfimevento": evento.dtfimevento,
            "nmlocalevento": evento.nmlocalevento,
            "dsendlocevento": evento.dsendlocevento,
            "urlbannerevento": f"{evento.urlbannerevento}" if evento.urlbannerevento else None,
            "statusevento": evento.statusevento,
        }
        for evento in eventos
    ]


@router.get("/{evento_id}")
def get_evento_por_id(
    evento_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    evento = (
        db.query(Evento, Loja.nmloja, Loja.dsbairroloja, Loja.endloja, Loja.nrendeloja, Cidade.nmcidade, Estado.sgestado)
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .join(Cidade, Cidade.cidade_id == Loja.cidade_id)
        .join(Estado, Estado.estado_id == Cidade.estado_id)
        .join(Organizacao, Organizacao.organizacao_id == Evento.organizacao_id)
        .filter(Evento.evento_id == evento_id)
        .filter(Organizacao.sitorganizacao == "ATIVA")
        .first()
    )

    if not evento:
        raise HTTPException(status_code=404, detail="Evento não encontrado")

    evento_obj, nmloja, dsbairroloja, endloja, nrendloja, nmcidade, sgestado = evento

    lotes = (
        db.query(EventoLote)
        .filter(EventoLote.evento_id == evento_id)
        .order_by(EventoLote.lote_id.asc())
        .all()
    )
    atracoes = (
        db.query(EventoAtracao, Atracao)
        .join(Atracao, Atracao.atracao_id == EventoAtracao.atracao_id)
        .filter(EventoAtracao.evento_id == evento_id)
        .order_by(EventoAtracao.dtinicioatracao.asc())
        .all()
    )

    base_url = str(request.base_url).rstrip("/")

    endereco_evento = evento_obj.dsendlocevento or endloja
    numero_endereco_evento = None if evento_obj.dsendlocevento else nrendloja
    local_evento    = evento_obj.nmlocalevento or nmloja

    return {
        "evento_id": evento_obj.evento_id,
        "organizacao_id": evento_obj.organizacao_id,
        "loja_id": evento_obj.loja_id,
        "nmtituloevento": getattr(evento_obj, "nmtituloevento", None),
        "dtinicioevento": getattr(evento_obj, "dtinicioevento", None),
        "dtfimevento": getattr(evento_obj, "dtfimevento", None),
        "nmlocalevento": local_evento,
        "dsendlocevento": endereco_evento,
        "nrendlocevento": numero_endereco_evento,
        "dsdescevento": getattr(evento_obj, "dsdescevento", None),
        "dspoliticacancelamento": evento_obj.dspoliticacancelamento,
        "dspoliticareembolso": evento_obj.dspoliticareembolso,
        "dspoliticacashback": evento_obj.dspoliticacashback,
        "urlbannerevento": f"{evento_obj.urlbannerevento}" if getattr(evento_obj, "urlbannerevento", None) else None,
        "statusevento": getattr(evento_obj, "statusevento", None),
        "nmloja": nmloja,
        "nmcidade": nmcidade,
        "sgestado": sgestado,
        "dsbairroloja": dsbairroloja,
        "endloja": endloja,
        "atracoes": [
            {
                "atracao_id": atracao.atracao_id,
                "nmatracao": atracao.nmatracao,
                "dsestilomusical": atracao.dsestilomusical,
                "estilos": [
                    {
                        "estilomusical_id": estilo.organizacaoestilomusical_id,
                        "nmestilomusical": estilo.nmestilomusical,
                    }
                    for estilo in atracao.estilos
                ],
                "dsatracao": atracao.dsatracao,
                "urlbanneratracao": atracao.urlbanneratracao,
                "dtinicioatracao": programacao.dtinicioatracao,
                "dtfimatracao": programacao.dtfimatracao,
            }
            for programacao, atracao in atracoes
        ],
        "lotes": [
            {
                "lote_id": lista_lotes.lote_id,
                "nmlote": getattr(lista_lotes, "nmlote", None),
                "vrprecolote": float(getattr(lista_lotes, "vrprecolote", 0) or 0),
                "qttotallote": getattr(lista_lotes, "qttotallote", None),
                "qtvendidalote": getattr(lista_lotes, "qtvendidalote", None),
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
    dspoliticacancelamento: str | None = Form(None),
    dspoliticareembolso: str | None = Form(None),
    dspoliticacashback: str | None = Form(None),
    dtinicioevento: str = Form(...),
    dtfimevento: str | None = Form(None),
    nmlocalevento: str | None = Form(None),
    dsendlocevento: str | None = Form(None),
    statusevento: str = Form("RASCUNHO"),
    urlbannerevento: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    try:
        inicio_evento = datetime.fromisoformat(dtinicioevento)
        if inicio_evento.date() < datetime.now().date():
            raise HTTPException(
                status_code=422,
                detail="Não é permitido criar eventos em datas passadas.",
            )

        loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
        if not loja:
            raise HTTPException(status_code=404, detail="Loja não encontrada")
        validar_mutacao_loja(usuario, loja.organizacao_id, loja_id)
        if statusevento.upper() == 'ATIVO':
            validar_publicacao_loja(db, loja_id)

        banner_url = salvar_banner_evento(urlbannerevento)

        novo = Evento(
            organizacao_id=organizacao_id,
            loja_id=loja_id,
            nmtituloevento=nmtituloevento,
            dsdescevento=dsdescevento,
            dspoliticacancelamento=dspoliticacancelamento,
            dspoliticareembolso=dspoliticareembolso,
            dspoliticacashback=dspoliticacashback,
            dtinicioevento=inicio_evento,
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
    dspoliticacancelamento: str | None = Form(None),
    dspoliticareembolso: str | None = Form(None),
    dspoliticacashback: str | None = Form(None),
    dtinicioevento: str | None = Form(None),
    dtfimevento: str | None = Form(None),
    nmlocalevento: str | None = Form(None),
    dsendlocevento: str | None = Form(None),
    statusevento: str | None = Form(None),
    urlbannerevento: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    try:
        evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()

        if not evento:
            raise HTTPException(status_code=404, detail="Evento não encontrado")
        validar_mutacao_loja(usuario, evento.organizacao_id, evento.loja_id)

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

        if dspoliticacancelamento is not None:
            evento.dspoliticacancelamento = dspoliticacancelamento

        if dspoliticareembolso is not None:
            evento.dspoliticareembolso = dspoliticareembolso

        if dspoliticacashback is not None:
            evento.dspoliticacashback = dspoliticacashback

        if dtinicioevento is not None:
            evento.dtinicioevento = datetime.fromisoformat(dtinicioevento)

        if dtfimevento is not None:
            evento.dtfimevento = datetime.fromisoformat(dtfimevento) if dtfimevento else None

        if nmlocalevento is not None:
            evento.nmlocalevento = nmlocalevento

        if dsendlocevento is not None:
            evento.dsendlocevento = dsendlocevento

        if statusevento is not None:
            if statusevento.upper() == 'ATIVO':
                validar_publicacao_loja(db, evento.loja_id)
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
                "dspoliticacancelamento": evento.dspoliticacancelamento,
                "dspoliticareembolso": evento.dspoliticareembolso,
                "dspoliticacashback": evento.dspoliticacashback,
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
def deletar_evento(
    evento_id: int,
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    try:
        evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()

        if not evento:
            raise HTTPException(status_code=404, detail="Evento não encontrado")
        validar_mutacao_loja(usuario, evento.organizacao_id, evento.loja_id)

        db.delete(evento)
        db.commit()

        return {"mensagem": "Evento deletado com sucesso"}

    except HTTPException:
        raise

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar evento: {str(e)}")

