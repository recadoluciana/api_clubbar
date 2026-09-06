from datetime import datetime
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.contratolead import LeadEstabelecimentoContrato
from app.models.contratopadrao import ContratoPadrao
from app.models.leadestabelecimento import LeadEstabelecimento
from app.models.leadparceiro import LeadParceiro
from app.services.portal_acesso_service import obter_lead_portal


router = APIRouter(prefix="/lead-estabelecimento-contratos", tags=["Contratos de estabelecimentos de leads"])
portal_router = APIRouter(prefix="/portal-parceiro", tags=["Portal do parceiro"])


class LeadEstabelecimentoContratoCreate(BaseModel):
    versao: str | None = Field(default=None, max_length=30)
    vrtaxaprod: float = Field(default=5, ge=0, le=100)
    vrtaxaing: float = Field(default=5, ge=0, le=100)


def _out(item: LeadEstabelecimentoContrato) -> dict:
    return {
        "leadestabelecimentocontrato_id": item.leadestabelecimentocontrato_id,
        "leadestabelecimento_id": item.leadestabelecimento_id,
        "contratopadrao_id": item.contratopadrao_id,
        "versao": item.versao,
        "status": item.status,
        "vrtaxaprod": float(item.vrtaxaprod),
        "vrtaxaing": float(item.vrtaxaing),
        "conteudocontrato": item.conteudocontrato,
        "hashdocumento": item.hashdocumento,
        "nmsignatario": item.nmsignatario,
        "cpfcnpjsignatario": item.cpfcnpjsignatario,
        "dtaceite": item.dtaceite,
        "dtdisponibilizacao": item.dtdisponibilizacao,
        "dtcriacao": item.dtcriacao,
    }


def _valor(valor: object | None, padrao: str = "não informado") -> str:
    texto = str(valor or "").strip()
    return texto or padrao


def _gerar_conteudo(
    estabelecimento: LeadEstabelecimento,
    lead: LeadParceiro,
    cidade: Cidade | None,
    estado: Estado | None,
    versao: str,
    taxa_produtos: float,
    taxa_ingressos: float,
    modelo: ContratoPadrao,
) -> str:
    complemento = f", {_valor(estabelecimento.complemento)}" if estabelecimento.complemento else ""
    endereco = (
        f"{_valor(estabelecimento.endereco)}, {_valor(estabelecimento.numero)}{complemento}, "
        f"bairro {_valor(estabelecimento.bairro)}, {_valor(getattr(cidade, 'nmcidade', None))}/"
        f"{_valor(getattr(estado, 'sgestado', None))}, CEP {_valor(estabelecimento.cep)}"
    )
    responsavel = _valor(estabelecimento.nmresponsavel, lead.nmresponsavel)
    telefone = _valor(estabelecimento.telefone_responsavel, estabelecimento.telefone or lead.telefone)
    email = _valor(estabelecimento.email_responsavel, estabelecimento.email or lead.email)
    valores = {
        "{{VERSAO}}": modelo.versao,
        "{{NOME_ESTABELECIMENTO}}": _valor(estabelecimento.nmestabelecimento),
        "{{CPF_CNPJ}}": _valor(estabelecimento.cpfcnpj),
        "{{RESPONSAVEL}}": responsavel,
        "{{TELEFONE}}": telefone,
        "{{EMAIL}}": email,
        "{{ENDERECO}}": endereco,
        "{{ATIVIDADE}}": _valor(estabelecimento.tipo),
        "{{MODALIDADE_VENDA}}": _valor(estabelecimento.tipovenda),
        "{{TAXA_PRODUTOS}}": f"{taxa_produtos:.2f}",
        "{{TAXA_INGRESSOS}}": f"{taxa_ingressos:.2f}",
        "{{TAXA_IMPLANTACAO}}": f"{float(modelo.vrimplantacao):.2f}",
    }
    conteudo = modelo.conteudomodelo
    for marcador, valor in valores.items():
        conteudo = conteudo.replace(marcador, valor)
    return conteudo.strip()


def _contexto_contrato(
    db: Session,
    leadestabelecimento_id: int,
    dados: LeadEstabelecimentoContratoCreate,
) -> tuple[LeadEstabelecimento, ContratoPadrao, str]:
    estabelecimento = db.query(LeadEstabelecimento).filter(
        LeadEstabelecimento.leadestabelecimento_id == leadestabelecimento_id
    ).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado.")
    lead = db.query(LeadParceiro).filter(
        LeadParceiro.leadparceiro_id == estabelecimento.leadparceiro_id
    ).first()
    cidade = db.query(Cidade).filter(Cidade.cidade_id == estabelecimento.cidade_id).first()
    estado = db.query(Estado).filter(Estado.estado_id == estabelecimento.estado_id).first()
    modelo = db.query(ContratoPadrao).filter(
        ContratoPadrao.sitcontrato == "ATIVO"
    ).order_by(ContratoPadrao.contratopadrao_id.desc()).first()
    if not modelo:
        raise HTTPException(422, "Cadastre e ative um contrato padrão antes de gerar contratos")
    return estabelecimento, modelo, _gerar_conteudo(
        estabelecimento,
        lead,
        cidade,
        estado,
        modelo.versao,
        dados.vrtaxaprod,
        dados.vrtaxaing,
        modelo,
    )


@router.get("/estabelecimento/{leadestabelecimento_id}")
def listar_contratos(
    leadestabelecimento_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    return [
        _out(item)
        for item in db.query(LeadEstabelecimentoContrato)
        .filter(LeadEstabelecimentoContrato.leadestabelecimento_id == leadestabelecimento_id)
        .order_by(LeadEstabelecimentoContrato.leadestabelecimentocontrato_id.desc())
        .all()
    ]


@router.post(
    "/estabelecimento/{leadestabelecimento_id}/previsualizar",
)
def previsualizar_contrato(
    leadestabelecimento_id: int,
    dados: LeadEstabelecimentoContratoCreate,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    _, _, conteudo = _contexto_contrato(db, leadestabelecimento_id, dados)
    return {"conteudocontrato": conteudo}


@router.post(
    "/estabelecimento/{leadestabelecimento_id}",
    status_code=status.HTTP_201_CREATED,
)
def criar_contrato(
    leadestabelecimento_id: int,
    dados: LeadEstabelecimentoContratoCreate,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    estabelecimento, modelo, conteudo = _contexto_contrato(
        db, leadestabelecimento_id, dados
    )
    item = LeadEstabelecimentoContrato(
        leadestabelecimento_id=leadestabelecimento_id,
        contratopadrao_id=modelo.contratopadrao_id,
        status="ENVIADO",
        versao=modelo.versao,
        vrtaxaprod=dados.vrtaxaprod,
        vrtaxaing=dados.vrtaxaing,
        conteudocontrato=conteudo,
        hashdocumento=sha256(conteudo.encode("utf-8")).hexdigest(),
        dtdisponibilizacao=datetime.now(),
    )
    estabelecimento.vrtaxaprod = dados.vrtaxaprod
    estabelecimento.vrtaxaing = dados.vrtaxaing
    db.add(item)
    db.commit()
    db.refresh(item)
    return _out(item)


@portal_router.patch("/contratos/{leadestabelecimentocontrato_id}/aceitar")
def aceitar_contrato(
    leadestabelecimentocontrato_id: int,
    request: Request,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    item = (
        db.query(LeadEstabelecimentoContrato)
        .join(
            LeadEstabelecimento,
            LeadEstabelecimento.leadestabelecimento_id
            == LeadEstabelecimentoContrato.leadestabelecimento_id,
        )
        .filter(
            LeadEstabelecimentoContrato.leadestabelecimentocontrato_id
            == leadestabelecimentocontrato_id,
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
