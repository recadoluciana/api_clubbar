#portalparceiro.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.leadagendamento import LeadAgendamento
from app.models.leadmaterial import LeadMaterial
from app.models.leadmensagem import LeadMensagem
from app.models.leadparceiro import LeadParceiro
from app.schemas.portalparceiro import (
    PortalAgendamentoResposta,
    PortalDecisaoUpdate,
    PortalMensagemCreate,
)
from app.services.portal_acesso_service import obter_lead_portal


router = APIRouter(
    prefix="/portal-parceiro",
    tags=["Portal do parceiro"],
)


@router.get("/resumo")
def obter_resumo(
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    mensagens_nao_lidas = (
        db.query(func.count(LeadMensagem.leadmensagem_id))
        .filter(
            LeadMensagem.leadparceiro_id == lead.leadparceiro_id,
            LeadMensagem.origem == "CLUBBAR",
            LeadMensagem.lida == "N",
        )
        .scalar()
        or 0
    )

    agendamentos_pendentes = (
        db.query(func.count(LeadAgendamento.leadagendamento_id))
        .filter(
            LeadAgendamento.leadparceiro_id == lead.leadparceiro_id,
            LeadAgendamento.status == "PENDENTE",
        )
        .scalar()
        or 0
    )

    materiais = (
        db.query(func.count(LeadMaterial.leadmaterial_id))
        .filter(LeadMaterial.leadparceiro_id == lead.leadparceiro_id)
        .scalar()
        or 0
    )

    return {
        "leadparceiro_id": lead.leadparceiro_id,
        "nmresponsavel": lead.nmresponsavel,
        "nmestabelecimento": lead.nmestabelecimento,
        "tipo": lead.tipo,
        "tipovenda": lead.tipovenda,
        "status": lead.status,
        "decisao": lead.decisao,
        "mensagens_nao_lidas": int(mensagens_nao_lidas),
        "agendamentos_pendentes": int(agendamentos_pendentes),
        "materiais": int(materiais),
    }


@router.get("/mensagens")
def listar_mensagens(
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    mensagens = (
        db.query(LeadMensagem)
        .filter(LeadMensagem.leadparceiro_id == lead.leadparceiro_id)
        .order_by(
            LeadMensagem.dtcriacao.asc(),
            LeadMensagem.leadmensagem_id.asc(),
        )
        .all()
    )

    alterou = False
    for mensagem in mensagens:
        if mensagem.origem == "CLUBBAR" and mensagem.lida == "N":
            mensagem.lida = "S"
            alterou = True

    if alterou:
        db.commit()

    return [
        {
            "leadmensagem_id": item.leadmensagem_id,
            "origem": item.origem,
            "mensagem": item.mensagem,
            "lida": item.lida,
            "dtcriacao": item.dtcriacao,
        }
        for item in mensagens
    ]


@router.post("/mensagens", status_code=status.HTTP_201_CREATED)
def enviar_mensagem(
    dados: PortalMensagemCreate,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    mensagem = LeadMensagem(
        leadparceiro_id=lead.leadparceiro_id,
        origem="LEAD",
        mensagem=dados.mensagem.strip(),
        lida="N",
    )

    db.add(mensagem)
    db.commit()
    db.refresh(mensagem)

    return {
        "leadmensagem_id": mensagem.leadmensagem_id,
        "origem": mensagem.origem,
        "mensagem": mensagem.mensagem,
        "lida": mensagem.lida,
        "dtcriacao": mensagem.dtcriacao,
    }


@router.get("/agendamentos")
def listar_agendamentos(
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    itens = (
        db.query(LeadAgendamento)
        .filter(LeadAgendamento.leadparceiro_id == lead.leadparceiro_id)
        .order_by(
            LeadAgendamento.dtagendamento.desc(),
            LeadAgendamento.leadagendamento_id.desc(),
        )
        .all()
    )

    return [
        {
            "leadagendamento_id": item.leadagendamento_id,
            "tipo": item.tipo,
            "dtagendamento": item.dtagendamento,
            "observacao": item.observacao,
            "status": item.status,
            "dtcriacao": item.dtcriacao,
        }
        for item in itens
    ]


@router.patch("/agendamentos/{leadagendamento_id}/resposta")
def responder_agendamento(
    leadagendamento_id: int,
    dados: PortalAgendamentoResposta,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    agendamento = (
        db.query(LeadAgendamento)
        .filter(
            LeadAgendamento.leadagendamento_id == leadagendamento_id,
            LeadAgendamento.leadparceiro_id == lead.leadparceiro_id,
        )
        .first()
    )

    if agendamento is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agendamento não encontrado.",
        )

    if agendamento.status != "PENDENTE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Este agendamento já foi respondido ou encerrado.",
        )

    agendamento.status = dados.status
    db.commit()
    db.refresh(agendamento)

    return {
        "ok": True,
        "leadagendamento_id": agendamento.leadagendamento_id,
        "status": agendamento.status,
    }


@router.get("/materiais")
def listar_materiais(
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    itens = (
        db.query(LeadMaterial)
        .filter(LeadMaterial.leadparceiro_id == lead.leadparceiro_id)
        .order_by(
            LeadMaterial.dtcriacao.desc(),
            LeadMaterial.leadmaterial_id.desc(),
        )
        .all()
    )

    return [
        {
            "leadmaterial_id": item.leadmaterial_id,
            "titulo": item.titulo,
            "descricao": item.descricao,
            "tipo": item.tipo,
            "urlarquivo": item.urlarquivo,
            "dtcriacao": item.dtcriacao,
        }
        for item in itens
    ]


@router.patch("/decisao")
def registrar_decisao(
    dados: PortalDecisaoUpdate,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    if lead.status == "CONVERTIDO":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A parceria já foi convertida e não pode ser alterada.",
        )

    lead.decisao = dados.decisao
    if dados.decisao == 'ACEITOU':
        lead.status = 'APROVADO_CADASTRO'
    elif dados.decisao == 'RECUSOU':
        lead.status = 'PERDIDO'
    else:
        lead.status = 'NEGOCIANDO'
    db.commit()

    return {
        "ok": True,
        "decisao": lead.decisao,
        "mensagem": "Decisão registrada com sucesso.",
    }
