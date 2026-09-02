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
from app.models.leadestabelecimento import LeadEstabelecimento
from app.models.leadparceiro import LeadParceiro
from app.services.portal_acesso_service import obter_lead_portal


router = APIRouter(prefix="/lead-estabelecimento-contratos", tags=["Contratos de estabelecimentos de leads"])
portal_router = APIRouter(prefix="/portal-parceiro", tags=["Portal do parceiro"])


class LeadEstabelecimentoContratoCreate(BaseModel):
    versao: str = Field(min_length=1, max_length=30)
    vrtaxaprod: float = Field(default=5, ge=0, le=100)
    vrtaxaing: float = Field(default=5, ge=0, le=100)


def _out(item: LeadEstabelecimentoContrato) -> dict:
    return {
        "leadestabelecimentocontrato_id": item.leadestabelecimentocontrato_id,
        "leadestabelecimento_id": item.leadestabelecimento_id,
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
    return f"""TERMO DE PARCERIA COMERCIAL CLUBBAR
Versão {versao}

ESTABELECIMENTO PARCEIRO
Nome: {_valor(estabelecimento.nmestabelecimento)}
CPF/CNPJ: {_valor(estabelecimento.cpfcnpj)}
Responsável: {responsavel}
Telefone: {telefone}
E-mail: {email}
Endereço: {endereco}
Atividade: {_valor(estabelecimento.tipo)}
Modalidade de venda: {_valor(estabelecimento.tipovenda)}

1. OBJETO
O presente termo estabelece a parceria comercial para utilização da plataforma Clubbar pelo ESTABELECIMENTO PARCEIRO, incluindo a divulgação e a comercialização dos produtos e/ou ingressos indicados em seu cadastro.

2. RESPONSABILIDADES DO ESTABELECIMENTO
O ESTABELECIMENTO PARCEIRO declara que os dados informados são verdadeiros e compromete-se a manter atualizadas as informações, preços, disponibilidade, atendimento ao consumidor e demais obrigações relacionadas aos produtos, serviços ou eventos oferecidos.

3. TAXAS
Pelas vendas realizadas por meio da plataforma, serão aplicadas as seguintes taxas:
- Produtos: {taxa_produtos:.2f}% sobre o valor da venda.
- Ingressos: {taxa_ingressos:.2f}% sobre o valor da venda.

4. REPASSES E CANCELAMENTOS
Os repasses financeiros, cancelamentos, estornos e contestações observarão as regras operacionais e os prazos apresentados pela Clubbar e aceitos pelo ESTABELECIMENTO PARCEIRO.

5. USO DA PLATAFORMA
O ESTABELECIMENTO PARCEIRO é responsável pelo uso de suas credenciais e pelas informações publicadas. A Clubbar poderá suspender o acesso em caso de uso indevido, fraude, descumprimento deste termo ou obrigação legal.

6. PROTEÇÃO DE DADOS
As partes comprometem-se a tratar dados pessoais somente para as finalidades da parceria, observando a legislação aplicável de proteção de dados.

7. VIGÊNCIA E ENCERRAMENTO
Este termo entra em vigor na data do aceite eletrônico e permanece válido por prazo indeterminado, podendo ser encerrado por qualquer das partes, sem prejuízo das obrigações já constituídas.

8. ACEITE ELETRÔNICO
O responsável declara ter lido e concordado com o conteúdo integral deste termo. O aceite eletrônico, acompanhado de data, identificação do signatário e registro técnico, será armazenado como comprovação da concordância.

Ao aceitar, o responsável {responsavel} confirma sua concordância em nome do estabelecimento {_valor(estabelecimento.nmestabelecimento)}.
""".strip()


def _contexto_contrato(
    db: Session,
    leadestabelecimento_id: int,
    dados: LeadEstabelecimentoContratoCreate,
) -> tuple[LeadEstabelecimento, str]:
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
    return estabelecimento, _gerar_conteudo(
        estabelecimento,
        lead,
        cidade,
        estado,
        dados.versao,
        dados.vrtaxaprod,
        dados.vrtaxaing,
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
    _, conteudo = _contexto_contrato(db, leadestabelecimento_id, dados)
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
    estabelecimento, conteudo = _contexto_contrato(
        db, leadestabelecimento_id, dados
    )
    item = LeadEstabelecimentoContrato(
        leadestabelecimento_id=leadestabelecimento_id,
        status="ENVIADO",
        versao=dados.versao,
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
