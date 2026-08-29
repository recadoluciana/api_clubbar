from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.models.contratolead import ContratoLead
from app.models.leadestabelecimento import LeadEstabelecimento
from app.models.leadparceiro import LeadParceiro
from app.services.portal_acesso_service import obter_lead_portal


router = APIRouter(prefix="/contratos-lead", tags=["Contratos de leads"])
portal_router = APIRouter(prefix="/portal-parceiro", tags=["Portal do parceiro"])


class ContratoLeadCreate(BaseModel):
    versao: str = Field(min_length=1, max_length=30)
    vrtaxaprod: float = Field(default=5, ge=0, le=100)
    vrtaxaing: float = Field(default=5, ge=0, le=100)
    urlcontrato: str = Field(min_length=5, max_length=2000)
    hashdocumento: str | None = Field(default=None, min_length=64, max_length=64)


def _out(item: ContratoLead) -> dict:
    return {
        "contratolead_id": item.contratolead_id,
        "leadestabelecimento_id": item.leadestabelecimento_id,
        "versao": item.versao,
        "status": item.status,
        "vrtaxaprod": float(item.vrtaxaprod),
        "vrtaxaing": float(item.vrtaxaing),
        "urlcontrato": item.urlcontrato,
        "hashdocumento": item.hashdocumento,
        "nmsignatario": item.nmsignatario,
        "cpfcnpjsignatario": item.cpfcnpjsignatario,
        "dtaceite": item.dtaceite,
        "dtcriacao": item.dtcriacao,
    }


@router.get("/estabelecimento/{leadestabelecimento_id}")
def listar_contratos(
    leadestabelecimento_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    return [
        _out(item)
        for item in db.query(ContratoLead)
        .filter(ContratoLead.leadestabelecimento_id == leadestabelecimento_id)
        .order_by(ContratoLead.contratolead_id.desc())
        .all()
    ]


@router.post(
    "/estabelecimento/{leadestabelecimento_id}",
    status_code=status.HTTP_201_CREATED,
)
def criar_contrato(
    leadestabelecimento_id: int,
    dados: ContratoLeadCreate,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    estabelecimento = db.query(LeadEstabelecimento).filter(
        LeadEstabelecimento.leadestabelecimento_id == leadestabelecimento_id
    ).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado.")
    item = ContratoLead(
        leadestabelecimento_id=leadestabelecimento_id,
        status="ENVIADO",
        **dados.model_dump(),
    )
    estabelecimento.vrtaxaprod = dados.vrtaxaprod
    estabelecimento.vrtaxaing = dados.vrtaxaing
    db.add(item)
    db.commit()
    db.refresh(item)
    return _out(item)


@portal_router.patch("/contratos/{contratolead_id}/aceitar")
def aceitar_contrato(
    contratolead_id: int,
    request: Request,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    item = (
        db.query(ContratoLead)
        .join(
            LeadEstabelecimento,
            LeadEstabelecimento.leadestabelecimento_id
            == ContratoLead.leadestabelecimento_id,
        )
        .filter(
            ContratoLead.contratolead_id == contratolead_id,
            LeadEstabelecimento.leadparceiro_id == lead.leadparceiro_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")
    if item.status == "ACEITO":
        return _out(item)
    item.status = "ACEITO"
    item.nmsignatario = lead.nmresponsavel
    item.ipaceite = request.client.host if request.client else None
    item.dtaceite = datetime.now()
    db.commit()
    db.refresh(item)
    return _out(item)
