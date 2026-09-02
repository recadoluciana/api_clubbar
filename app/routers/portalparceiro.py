#portalparceiro.py
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.leadagendamento import LeadAgendamento
from app.models.leadmaterial import LeadMaterial
from app.models.leadmensagem import LeadMensagem
from app.models.leadparceiro import LeadParceiro
from app.models.leadestabelecimento import LeadEstabelecimento
from app.models.cidade import Cidade
from app.models.contratolead import LeadEstabelecimentoContrato
from app.schemas.portalparceiro import (
    PortalAgendamentoResposta,
    PortalStatusUpdate,
    PortalMensagemCreate,
    PortalEstabelecimentoCreate,
    PortalLoginLead,
)
from app.services.portal_acesso_service import criar_acesso_portal, obter_lead_portal


router = APIRouter(
    prefix="/portal-parceiro",
    tags=["Portal do parceiro"],
)


@router.post("/entrar")
def entrar_portal(dados: PortalLoginLead, db: Session = Depends(get_db)):
    telefone = "".join(caractere for caractere in dados.telefone if caractere.isdigit())
    lead = (
        db.query(LeadParceiro)
        .filter(LeadParceiro.email == str(dados.email).strip().lower())
        .order_by(LeadParceiro.leadparceiro_id.desc())
        .first()
    )
    telefone_cadastrado = (
        "".join(caractere for caractere in (lead.telefone if lead else "") if caractere.isdigit())
    )
    if lead is None or telefone != telefone_cadastrado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-mail ou telefone não conferem com o cadastro.",
        )

    token = criar_acesso_portal(db, leadparceiro_id=lead.leadparceiro_id)
    db.commit()
    return {"acesso": token}


@router.post("/estabelecimentos", status_code=status.HTTP_201_CREATED)
def cadastrar_estabelecimento(
    dados: PortalEstabelecimentoCreate,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    cidade = db.query(Cidade).filter(Cidade.cidade_id == dados.cidade_id).first()
    if not cidade or cidade.estado_id != dados.estado_id:
        raise HTTPException(
            status_code=422,
            detail="Cidade e estado informados são incompatíveis.",
        )
    documento = "".join(c for c in (dados.cpfcnpj or "") if c.isdigit()) or None
    item = LeadEstabelecimento(
        leadparceiro_id=lead.leadparceiro_id,
        nmestabelecimento=dados.nmestabelecimento.strip(),
        tipo=dados.tipo,
        tipovenda=dados.tipovenda,
        cpfcnpj=documento,
        telefone=dados.telefone or lead.telefone,
        email=str(dados.email).lower() if dados.email else lead.email,
        estado_id=dados.estado_id,
        cidade_id=dados.cidade_id,
        cep=dados.cep,
        endereco=dados.endereco,
        numero=dados.numero,
        complemento=dados.complemento,
        bairro=dados.bairro,
        mensagem=(dados.mensagem or "").strip() or None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "leadestabelecimento_id": item.leadestabelecimento_id,
        "nmestabelecimento": item.nmestabelecimento,
        "status": item.status,
    }


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

    mensagens_recebidas = (
        db.query(func.count(LeadMensagem.leadmensagem_id))
        .filter(
            LeadMensagem.leadparceiro_id == lead.leadparceiro_id,
            LeadMensagem.origem == "CLUBBAR",
        )
        .scalar()
        or 0
    )

    mensagens_enviadas = (
        db.query(func.count(LeadMensagem.leadmensagem_id))
        .filter(
            LeadMensagem.leadparceiro_id == lead.leadparceiro_id,
            LeadMensagem.origem == "LEAD",
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

    agendamentos = (
        db.query(func.count(LeadAgendamento.leadagendamento_id))
        .filter(LeadAgendamento.leadparceiro_id == lead.leadparceiro_id)
        .scalar()
        or 0
    )

    materiais = (
        db.query(func.count(LeadMaterial.leadmaterial_id))
        .filter(LeadMaterial.leadparceiro_id == lead.leadparceiro_id)
        .scalar()
        or 0
    )

    estabelecimentos = (
        db.query(LeadEstabelecimento)
        .filter(LeadEstabelecimento.leadparceiro_id == lead.leadparceiro_id)
        .order_by(LeadEstabelecimento.leadestabelecimento_id.asc())
        .all()
    )
    contratos_por_estabelecimento: dict[int, list[dict]] = {}
    ids_estabelecimentos = [item.leadestabelecimento_id for item in estabelecimentos]
    if ids_estabelecimentos:
        contratos = (
            db.query(LeadEstabelecimentoContrato)
            .filter(LeadEstabelecimentoContrato.leadestabelecimento_id.in_(ids_estabelecimentos))
            .order_by(LeadEstabelecimentoContrato.leadestabelecimentocontrato_id.desc())
            .all()
        )
        for contrato in contratos:
            contratos_por_estabelecimento.setdefault(
                contrato.leadestabelecimento_id, []
            ).append(
                {
                    "leadestabelecimentocontrato_id": contrato.leadestabelecimentocontrato_id,
                    "versao": contrato.versao,
                    "status": contrato.status,
                    "conteudocontrato": contrato.conteudocontrato,
                    "vrtaxaprod": float(contrato.vrtaxaprod),
                    "vrtaxaing": float(contrato.vrtaxaing),
                    "dtaceite": contrato.dtaceite,
                }
            )

    return {
        "leadparceiro_id": lead.leadparceiro_id,
        "nmresponsavel": lead.nmresponsavel,
        "nmorganizacao": lead.nmorganizacao,
        "nmestabelecimento": estabelecimentos[0].nmestabelecimento if estabelecimentos else "",
        "tipo": estabelecimentos[0].tipo if estabelecimentos else "BAR",
        "tipovenda": estabelecimentos[0].tipovenda if estabelecimentos else "AMBOS",
        "mensagens_nao_lidas": int(mensagens_nao_lidas),
        "mensagens_recebidas": int(mensagens_recebidas),
        "mensagens_enviadas": int(mensagens_enviadas),
        "agendamentos_pendentes": int(agendamentos_pendentes),
        "agendamentos": int(agendamentos),
        "materiais": int(materiais),
        "estabelecimentos": [
            {
                "leadestabelecimento_id": item.leadestabelecimento_id,
                "nmestabelecimento": item.nmestabelecimento,
                "nmresponsavel": item.nmresponsavel or lead.nmresponsavel,
                "telefone_responsavel": item.telefone_responsavel or lead.telefone,
                "email_responsavel": item.email_responsavel or lead.email,
                "tipo": item.tipo,
                "tipovenda": item.tipovenda,
                "status": item.status.value if hasattr(item.status, "value") else item.status,
                "vrtaxaprod": float(item.vrtaxaprod),
                "vrtaxaing": float(item.vrtaxaing),
                "contratos": contratos_por_estabelecimento.get(
                    item.leadestabelecimento_id, []
                ),
            }
            for item in estabelecimentos
        ],
    }


@router.get("/mensagens")
def listar_mensagens(
    leadestabelecimento_id: int,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    mensagens = (
        db.query(LeadMensagem)
        .filter(
            LeadMensagem.leadparceiro_id == lead.leadparceiro_id,
            LeadMensagem.leadestabelecimento_id == leadestabelecimento_id,
        )
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
    leadestabelecimento_id: int,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    estabelecimento = db.query(LeadEstabelecimento).filter(
        LeadEstabelecimento.leadestabelecimento_id == leadestabelecimento_id,
        LeadEstabelecimento.leadparceiro_id == lead.leadparceiro_id,
    ).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado.")
    mensagem = LeadMensagem(
        leadparceiro_id=lead.leadparceiro_id,
        leadestabelecimento_id=leadestabelecimento_id,
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
    leadestabelecimento_id: int,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    itens = (
        db.query(LeadAgendamento)
        .filter(
            LeadAgendamento.leadparceiro_id == lead.leadparceiro_id,
            LeadAgendamento.leadestabelecimento_id == leadestabelecimento_id,
        )
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
    leadestabelecimento_id: int,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    itens = (
        db.query(LeadMaterial)
        .filter(
            LeadMaterial.leadparceiro_id == lead.leadparceiro_id,
            LeadMaterial.leadestabelecimento_id == leadestabelecimento_id,
        )
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


@router.patch("/status")
def registrar_status(
    dados: PortalStatusUpdate,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    consulta = db.query(LeadEstabelecimento).filter(
        LeadEstabelecimento.leadparceiro_id == lead.leadparceiro_id
    )
    if dados.leadestabelecimento_id is not None:
        consulta = consulta.filter(
            LeadEstabelecimento.leadestabelecimento_id
            == dados.leadestabelecimento_id
        )
    estabelecimento = consulta.order_by(
        LeadEstabelecimento.leadestabelecimento_id.asc()
    ).first()
    if estabelecimento is None:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado.")

    status_atual = (
        estabelecimento.status.value
        if hasattr(estabelecimento.status, "value")
        else estabelecimento.status
    )
    if status_atual == "CONVERTIDO":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A parceria já foi convertida e não pode ser alterada.",
        )

    if dados.status == "ACEITOU_PARCERIA":
        contrato = (
            db.query(LeadEstabelecimentoContrato)
            .filter(
                LeadEstabelecimentoContrato.leadestabelecimento_id
                == estabelecimento.leadestabelecimento_id
            )
            .order_by(LeadEstabelecimentoContrato.leadestabelecimentocontrato_id.desc())
            .first()
        )
        if not contrato or contrato.status != "ACEITO":
            raise HTTPException(
                status_code=409,
                detail="Leia e aceite o contrato deste estabelecimento antes de aceitar a parceria.",
            )

    estabelecimento.status = dados.status
    if dados.status == 'ACEITOU_PARCERIA':
        estabelecimento.dtaceite = datetime.now()
    db.commit()

    return {
        "ok": True,
        "leadestabelecimento_id": estabelecimento.leadestabelecimento_id,
        "status": estabelecimento.status,
        "mensagem": "Status registrado com sucesso.",
    }
