from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
import os
import uuid
import shutil
import traceback

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_usuario_logado
from app.core.permissoes_loja import validar_mutacao_loja
from app.models.loja import Loja
from app.services.agenda_service import obter_ou_criar_agenda
from app.models.evento import Evento
from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.eventolote import EventoLote
from app.models.eventoloteglobal import EventoLoteGlobal
from app.models.eventolotepreco import EventoLotePreco
from app.models.eventosetor import EventoSetor
from app.models.eventoatracao import EventoAtracao
from app.models.atracao import Atracao
from app.models.organizacao import Organizacao
from app.models.lojapoliticaingresso import LojaPoliticaIngresso
from app.models.venda import Venda
from app.models.itvenda import ItVenda
from app.models.usuario import Usuario
from app.schemas.evento import EventoOutBR
from app.core.config import UPLOAD_EVENTOS
from app.services.evento_imagem_service import imagem_evento
from app.services.evento_disponibilidade_service import (
    validar_evento_unico_por_loja_data_local,
)
from app.services.evento_edicao_service import validar_evento_editavel
from app.services.onboarding_parceiro_service import validar_publicacao_loja

router = APIRouter(prefix="/eventos", tags=["eventos"])

STATUS_EVENTO_VALIDOS = {"RASCUNHO", "ATIVO", "INATIVO", "ENCERRADO", "CANCELADO"}


class CapacidadeEventoIn(BaseModel):
    qtcapacidadeevento: int = Field(gt=0)


class PublicarEventosIn(BaseModel):
    evento_ids: list[int] = Field(min_length=1)


def _resumo_capacidade_evento(db: Session, evento: Evento) -> dict:
    capacidade_setores = int(
        db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0))
        .filter(
            EventoSetor.evento_id == evento.evento_id,
            EventoSetor.sitsetor == "ATIVO",
        )
        .scalar()
        or 0
    )
    capacidade_evento = (
        int(evento.qtcapacidadeevento)
        if evento.qtcapacidadeevento is not None
        else None
    )
    return {
        "evento_id": evento.evento_id,
        "qtcapacidadeevento": capacidade_evento,
        "qtcapacidade_setores": capacidade_setores,
        "qtcapacidade_nao_distribuida": (
            capacidade_evento - capacidade_setores
            if capacidade_evento is not None
            else None
        ),
    }


def _evento_gerenciavel(db: Session, evento_id: int, usuario) -> Evento:
    evento = db.query(Evento).filter(Evento.evento_id == evento_id).first()
    if not evento:
        raise HTTPException(404, "Evento não encontrado.")
    validar_mutacao_loja(usuario, evento.organizacao_id, evento.loja_id)
    return evento


def _eventos_gerenciaveis(
    db: Session,
    evento_ids: list[int],
    usuario: dict,
) -> list[Evento]:
    ids = list(dict.fromkeys(evento_ids))
    eventos = db.query(Evento).filter(Evento.evento_id.in_(ids)).all()
    encontrados = {evento.evento_id for evento in eventos}
    ausentes = [evento_id for evento_id in ids if evento_id not in encontrados]
    if ausentes:
        raise HTTPException(404, "Um ou mais eventos não foram encontrados.")

    for evento in eventos:
        validar_mutacao_loja(usuario, evento.organizacao_id, evento.loja_id)
    return eventos


def _publicar_eventos(db: Session, eventos: list[Evento]) -> int:
    for evento in eventos:
        validar_evento_editavel(evento)
    bloqueados = [
        evento.nmtituloevento
        for evento in eventos
        if evento.statusevento in {"CANCELADO", "ENCERRADO"}
    ]
    if bloqueados:
        raise HTTPException(
            422,
            "Não é possível publicar evento cancelado ou encerrado.",
        )

    sem_lote = []
    for evento in eventos:
        lote_configurado = (
            db.query(EventoLote.lote_id)
            .join(
                EventoLoteGlobal,
                EventoLoteGlobal.loteglobal_id == EventoLote.loteglobal_id,
            )
            .join(
                EventoSetor,
                EventoSetor.eventosetor_id == EventoLote.eventosetor_id,
            )
            .join(
                EventoLotePreco,
                EventoLotePreco.lote_id == EventoLote.lote_id,
            )
            .filter(
                EventoLoteGlobal.evento_id == evento.evento_id,
                EventoLoteGlobal.situacao == "ATIVO",
                EventoLote.situacao == "ATIVO",
                EventoSetor.sitsetor == "ATIVO",
                EventoLote.qtlimite > 0,
                EventoLotePreco.situacao == "ATIVO",
            )
            .first()
        )
        if lote_configurado is None:
            sem_lote.append(evento.nmtituloevento)

    if sem_lote:
        if len(sem_lote) == 1:
            detalhe = f"o evento '{sem_lote[0]}'"
        else:
            detalhe = "os eventos " + ", ".join(
                f"'{nome}'" for nome in sem_lote
            )
        raise HTTPException(
            422,
            f"Cadastre ao menos um lote global ativo e configurado para venda antes de publicar {detalhe}.",
        )

    for loja_id in {evento.loja_id for evento in eventos}:
        validar_publicacao_loja(db, loja_id)

    publicados = 0
    for evento in eventos:
        if evento.statusevento != "ATIVO":
            evento.statusevento = "ATIVO"
            publicados += 1
    return publicados


def deslocar_programacao_atracoes(programacoes, deslocamento: timedelta) -> None:
    """Desloca a grade sem alterar a duração planejada de cada atração."""
    for programacao in programacoes:
        duracao_minutos = int(programacao.nrminutoduracao or 0)
        if duracao_minutos <= 0:
            duracao_minutos = max(
                1,
                int(
                    (programacao.dtfimatracao - programacao.dtinicioatracao)
                    .total_seconds()
                    // 60
                ),
            )
            programacao.nrminutoduracao = duracao_minutos
        programacao.dtinicioatracao += deslocamento
        programacao.dtfimatracao = programacao.dtinicioatracao + timedelta(
            minutes=duracao_minutos
        )


def normalizar_status_evento(valor: str) -> str:
    status = valor.strip().upper()
    if status not in STATUS_EVENTO_VALIDOS:
        raise HTTPException(status_code=422, detail="Status do evento inválido.")
    return status


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
    db: Session,
    ev: Evento,
    nmloja: str | None = None,
    nmcidade: str | None = None,
    urllogoloja: str | None = None,
    total_vendas_loja: int = 0,
    atracoes: list[dict] | None = None,
):
    return {
        "evento_id": ev.evento_id,
        "organizacao_id": ev.organizacao_id,
        "loja_id": ev.loja_id,
        "nmtituloevento": ev.nmtituloevento,
        "dsdescevento": ev.dsdescevento,
        "dspoliticacancelamento": ev.dspoliticacancelamento,
        "dtinicioevento": ev.dtinicioevento,
        "dtfimevento": ev.dtfimevento,
        "qtcapacidadeevento": ev.qtcapacidadeevento,
        "nmlocalevento": ev.nmlocalevento,
        "dsendlocevento": ev.dsendlocevento,
        "urlbannerevento": imagem_evento(db, ev),
        "statusevento": ev.statusevento,
        "nmloja": nmloja,
        "nmcidade": nmcidade,
        "urllogoloja": urllogoloja,
        "total_vendas_loja": total_vendas_loja,
        "atracoes": atracoes or [],
    }


def atracoes_resumo_por_evento(
    db: Session, evento_ids: list[int]
) -> dict[int, list[dict]]:
    """Agrupa as atrações dos cards sem executar uma consulta por evento."""
    resultado = {evento_id: [] for evento_id in evento_ids}
    if not evento_ids:
        return resultado

    programacoes = (
        db.query(EventoAtracao, Atracao)
        .join(Atracao, Atracao.atracao_id == EventoAtracao.atracao_id)
        .filter(EventoAtracao.evento_id.in_(evento_ids))
        .order_by(
            EventoAtracao.evento_id.asc(),
            EventoAtracao.dtinicioatracao.asc(),
            EventoAtracao.eventoatracao_id.asc(),
        )
        .all()
    )
    for programacao, atracao in programacoes:
        resultado.setdefault(programacao.evento_id, []).append(
            {
                "atracao_id": atracao.atracao_id,
                "nmatracao": atracao.nmatracao,
                "urlbanneratracao": atracao.urlbanneratracao,
            }
        )
    return resultado


@router.get("/{evento_id}/capacidade")
def obter_capacidade_evento(
    evento_id: int,
    payload=Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    return _resumo_capacidade_evento(db, _evento_gerenciavel(db, evento_id, payload))


@router.put("/{evento_id}/capacidade")
def atualizar_capacidade_evento(
    evento_id: int,
    dados: CapacidadeEventoIn,
    payload=Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    evento = _evento_gerenciavel(db, evento_id, payload)
    validar_evento_editavel(evento)
    capacidade_setores = int(
        db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0))
        .filter(
            EventoSetor.evento_id == evento.evento_id,
            EventoSetor.sitsetor == "ATIVO",
        )
        .scalar()
        or 0
    )
    if dados.qtcapacidadeevento < capacidade_setores:
        raise HTTPException(
            422,
            "A capacidade total não pode ser menor que a soma dos setores ativos "
            f"({capacidade_setores} pessoas).",
        )
    evento.qtcapacidadeevento = dados.qtcapacidadeevento
    db.commit()
    db.refresh(evento)
    return _resumo_capacidade_evento(db, evento)


def hoje_inicio_br() -> datetime:
    tz = ZoneInfo("America/Sao_Paulo")
    return datetime.combine(datetime.now(tz).date(), time.min).replace(tzinfo=None)


def filtro_evento_atual_ou_proximo(inicio_dia: datetime):
    """Inclui eventos que começam hoje/no futuro ou que ainda não terminaram."""
    return or_(
        Evento.dtinicioevento >= inicio_dia,
        Evento.dtfimevento >= inicio_dia,
    )


def _ticketman_logado(db: Session, payload: dict) -> Usuario:
    try:
        usuario_id = int(payload.get("sub") or 0)
    except (TypeError, ValueError):
        usuario_id = 0
    usuario = db.query(Usuario).filter(Usuario.usuario_id == usuario_id).first()
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado.")
    if (usuario.dscargo or "").upper() != "TICKETMAN":
        raise HTTPException(403, "Acesso exclusivo do Ticketman.")
    if not usuario.loja_id:
        raise HTTPException(403, "O Ticketman não está vinculado a um estabelecimento.")
    return usuario


def _endereco_loja(loja: Loja) -> str:
    partes = [loja.endloja, loja.nrendeloja, loja.complementoloja, loja.dsbairroloja]
    return ", ".join(str(parte).strip() for parte in partes if str(parte or "").strip())


def _resumo_leitor_ingressos(db: Session, evento: Evento, loja: Loja) -> dict:
    filtros = [
        EventoLote.evento_id == evento.evento_id,
        ItVenda.tipoitem == "INGRESSO",
        ItVenda.sititvenda == "ATIVO",
        Venda.sitvenda == "PAGA",
    ]
    vendidos = int(
        db.query(func.coalesce(func.sum(ItVenda.qtitvenda), 0))
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(*filtros)
        .scalar()
        or 0
    )
    validados = int(
        db.query(func.coalesce(func.sum(ItVenda.qtitvenda), 0))
        .join(EventoLote, EventoLote.lote_id == ItVenda.lote_id)
        .join(Venda, Venda.venda_id == ItVenda.venda_id)
        .filter(*filtros)
        .filter(ItVenda.identregaitvenda == "SIM")
        .scalar()
        or 0
    )
    local = (evento.nmlocalevento or "").strip() or loja.nmloja
    endereco = (evento.dsendlocevento or "").strip() or _endereco_loja(loja)
    return {
        "evento_id": evento.evento_id,
        "nmtituloevento": evento.nmtituloevento,
        "dtinicioevento": evento.dtinicioevento,
        "nmlocalevento": local,
        "dsendlocevento": endereco,
        "urlbannerevento": imagem_evento(db, evento),
        "vendidos": vendidos,
        "validados": validados,
        "faltam": max(0, vendidos - validados),
    }


@router.get("/leitor-ingressos/hoje")
def listar_eventos_do_dia_para_ticketman(
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    usuario = _ticketman_logado(db, payload)
    hoje = datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    inicio = datetime.combine(hoje, time.min)
    fim = inicio + timedelta(days=1)
    eventos = (
        db.query(Evento, Loja)
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .filter(Evento.loja_id == usuario.loja_id)
        .filter(Evento.statusevento == "ATIVO")
        .filter(Evento.dtinicioevento >= inicio, Evento.dtinicioevento < fim)
        .order_by(Evento.dtinicioevento.asc())
        .all()
    )
    return [_resumo_leitor_ingressos(db, evento, loja) for evento, loja in eventos]


@router.get("/{evento_id}/leitor-ingressos/resumo")
def resumo_evento_para_ticketman(
    evento_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    usuario = _ticketman_logado(db, payload)
    resultado = (
        db.query(Evento, Loja)
        .join(Loja, Loja.loja_id == Evento.loja_id)
        .filter(Evento.evento_id == evento_id, Evento.loja_id == usuario.loja_id)
        .first()
    )
    if resultado is None:
        raise HTTPException(404, "Evento não encontrado no estabelecimento.")
    return _resumo_leitor_ingressos(db, *resultado)


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

    atracoes = atracoes_resumo_por_evento(
        db, [ev.evento_id for ev, _, _ in eventos]
    )
    return [
        evento_to_out_br(
            db, ev, nmloja, nmcidade, atracoes=atracoes.get(ev.evento_id)
        )
        for ev, nmloja, nmcidade in eventos
    ]


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

    atracoes = atracoes_resumo_por_evento(
        db, [ev.evento_id for ev, *_ in eventos]
    )
    return [
        evento_to_out_br(
            db,
            ev,
            nmloja,
            nmcidade,
            urllogoloja,
            total_vendas_loja,
            atracoes.get(ev.evento_id),
        )
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
            "dtinicioevento": evento.dtinicioevento,
            "dtfimevento": evento.dtfimevento,
            "nmlocalevento": evento.nmlocalevento,
            "dsendlocevento": evento.dsendlocevento,
            "urlbannerevento": imagem_evento(db, evento),
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
    politica_loja = db.query(LojaPoliticaIngresso).filter(
        LojaPoliticaIngresso.loja_id == evento_obj.loja_id
    ).first()

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
        "politica_loja": {
            "dspoliticaingresso": politica_loja.dspoliticaingresso,
            "dsorientacoesacesso": politica_loja.dsorientacoesacesso,
        } if politica_loja else None,
        "urlbannerevento": imagem_evento(db, evento_obj),
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
                "nrminutoduracao": programacao.nrminutoduracao,
            }
            for programacao, atracao in atracoes
        ],
        "lotes": [
            {
                "lote_id": lista_lotes.lote_id,
                "nmlote": getattr(lista_lotes, "nmlote", None),
                "vrprecolote": float(lista_lotes.precos[0].vrpreco if lista_lotes.precos else 0),
                "qttotallote": getattr(lista_lotes, "qttotallote", None),
                "qtvendidalote": getattr(lista_lotes, "qtvendidalote", None),
                "statuslote": getattr(lista_lotes, "statuslote", None),
            }
            for lista_lotes in lotes
        ],
    }


@router.post("/publicar")
def publicar_eventos(
    dados: PublicarEventosIn,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    eventos = _eventos_gerenciaveis(db, dados.evento_ids, payload)
    publicados = _publicar_eventos(db, eventos)
    db.commit()
    return {
        "evento_ids": [evento.evento_id for evento in eventos],
        "mensagem": (
            f"{publicados} evento(s) publicado(s)."
            if publicados
            else "Os eventos selecionados já estão publicados."
        ),
    }


@router.post("/{evento_id}/publicar")
def publicar_evento(
    evento_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    evento = _evento_gerenciavel(db, evento_id, payload)
    publicados = _publicar_eventos(db, [evento])
    db.commit()
    return {
        "evento_id": evento.evento_id,
        "statusevento": evento.statusevento,
        "mensagem": (
            "Evento publicado com sucesso."
            if publicados
            else "Este evento já está publicado."
        ),
    }


@router.post("/{evento_id}/despublicar")
def despublicar_evento(
    evento_id: int,
    payload: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    evento = _evento_gerenciavel(db, evento_id, payload)
    validar_evento_editavel(evento)
    if evento.statusevento == "ATIVO":
        evento.statusevento = "RASCUNHO"
        db.commit()
        mensagem = "Publicação do evento retirada."
    else:
        mensagem = "Este evento já não está publicado."
    return {
        "evento_id": evento.evento_id,
        "statusevento": evento.statusevento,
        "mensagem": mensagem,
    }


@router.post("")
def criar_evento(
    organizacao_id: int = Form(...),
    loja_id: int = Form(...),
    nmtituloevento: str = Form(...),
    dsdescevento: str | None = Form(None),
    dspoliticacancelamento: str | None = Form(None),
    dtinicioevento: str = Form(...),
    dtfimevento: str | None = Form(None),
    nmlocalevento: str | None = Form(None),
    dsendlocevento: str | None = Form(None),
    statusevento: str = Form("RASCUNHO"),
    urlbannerevento: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    usuario: dict = Depends(get_usuario_logado),
):
    raise HTTPException(status_code=410, detail="Eventos devem ser criados a partir de um evento padrão.")
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
        status_evento = normalizar_status_evento(statusevento)

        banner_url = salvar_banner_evento(urlbannerevento)
        agenda = obter_ou_criar_agenda(
            db, loja.organizacao_id, loja_id, inicio_evento
        )

        novo = Evento(
            organizacao_id=organizacao_id,
            loja_id=loja_id,
            agendamensal_id=agenda.agendamensal_id,
            nmtituloevento=nmtituloevento,
            dsdescevento=dsdescevento,
            dspoliticacancelamento=dspoliticacancelamento,
            dtinicioevento=inicio_evento,
            dtfimevento=datetime.fromisoformat(dtfimevento) if dtfimevento else None,
            nmlocalevento=nmlocalevento,
            dsendlocevento=dsendlocevento,
            urlbannerevento=banner_url,
            statusevento=status_evento,
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
        validar_evento_editavel(evento)

        nova_loja_id = loja_id if loja_id is not None else evento.loja_id
        novo_inicio = (
            datetime.fromisoformat(dtinicioevento)
            if dtinicioevento is not None
            else evento.dtinicioevento
        )
        novo_local = (
            nmlocalevento if nmlocalevento is not None else evento.nmlocalevento
        )
        novo_status = (
            normalizar_status_evento(statusevento)
            if statusevento is not None
            else evento.statusevento
        )

        if novo_status != "CANCELADO" and any(
            valor is not None
            for valor in (loja_id, dtinicioevento, nmlocalevento, statusevento)
        ):
            validar_evento_unico_por_loja_data_local(
                db,
                loja_id=nova_loja_id,
                inicio=novo_inicio,
                local=novo_local,
                ignorar_evento_id=evento.evento_id,
            )

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

        deslocamento_atracoes = None
        if dtinicioevento is not None:
            deslocamento_atracoes = novo_inicio - evento.dtinicioevento
            evento.dtinicioevento = novo_inicio

        if deslocamento_atracoes and deslocamento_atracoes.total_seconds() != 0:
            programacoes = (
                db.query(EventoAtracao)
                .filter(EventoAtracao.evento_id == evento.evento_id)
                .order_by(EventoAtracao.dtinicioatracao)
                .all()
            )
            deslocar_programacao_atracoes(programacoes, deslocamento_atracoes)

        if dtfimevento is not None:
            evento.dtfimevento = datetime.fromisoformat(dtfimevento) if dtfimevento else None

        if nmlocalevento is not None:
            evento.nmlocalevento = nmlocalevento

        if dsendlocevento is not None:
            evento.dsendlocevento = dsendlocevento

        if statusevento is not None:
            evento.statusevento = novo_status

        if urlbannerevento is not None and urlbannerevento.filename:
            evento.urlbannerevento = salvar_banner_evento(urlbannerevento)

        agenda = obter_ou_criar_agenda(
            db,
            evento.organizacao_id,
            evento.loja_id,
            evento.dtinicioevento,
        )
        evento.agendamensal_id = agenda.agendamensal_id

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
        validar_evento_editavel(evento)

        # A exclusão representa apenas esta ocorrência da agenda. O modelo e
        # as demais datas recorrentes permanecem intactos.
        for lote_global in db.query(EventoLoteGlobal).filter(EventoLoteGlobal.evento_id == evento_id).all():
            db.delete(lote_global)
        db.flush()
        db.delete(evento)
        db.commit()

        return {"mensagem": "Evento removido desta data com sucesso"}

    except HTTPException:
        raise

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Esta data não pode ser excluída porque já possui reservas, vendas ou ingressos vinculados.")

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erro ao deletar evento: {str(e)}")

