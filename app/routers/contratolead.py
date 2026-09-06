from datetime import datetime
from html import escape
from io import BytesIO
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.contratolead import LeadEstabelecimentoContrato
from app.models.contratopadrao import ContratoPadrao
from app.models.leadestabelecimento import LeadEstabelecimento, StatusLeadEstabelecimento
from app.models.leadmensagem import LeadMensagem
from app.models.leadparceiro import LeadParceiro
from app.models.cobrancaimplantacao import CobrancaImplantacao
from app.services.portal_acesso_service import obter_lead_portal
from app.services.implantacao_service import criar_cobranca_implantacao, reconciliar_cobranca_implantacao, saida_cobranca
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer


router = APIRouter(prefix="/lead-estabelecimento-contratos", tags=["Contratos de estabelecimentos de leads"])
portal_router = APIRouter(prefix="/portal-parceiro", tags=["Portal do parceiro"])


class LeadEstabelecimentoContratoCreate(BaseModel):
    versao: str | None = Field(default=None, max_length=30)
    vrtaxaprod: float = Field(default=5, ge=0, le=100)
    vrtaxaing: float = Field(default=5, ge=0, le=100)
    cpfcnpj: str = Field(min_length=11, max_length=18)
    nmrazaosocial: str = Field(min_length=2, max_length=160)


class IsencaoImplantacaoIn(BaseModel):
    justificativa: str = Field(min_length=10, max_length=500)


@portal_router.get("/contratos/{leadestabelecimentocontrato_id}/pdf")
def contrato_pdf_portal(
    leadestabelecimentocontrato_id: int,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    contrato = db.query(LeadEstabelecimentoContrato).join(LeadEstabelecimento).filter(
        LeadEstabelecimentoContrato.leadestabelecimentocontrato_id == leadestabelecimentocontrato_id,
        LeadEstabelecimento.leadparceiro_id == lead.leadparceiro_id,
    ).first()
    if not contrato:
        raise HTTPException(404, "Contrato não encontrado")
    arquivo = BytesIO()
    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloClubbar", parent=estilos["Title"], alignment=TA_CENTER,
        fontName="Helvetica-Bold", fontSize=16, leading=20, spaceAfter=10,
    )
    corpo = ParagraphStyle(
        "CorpoContrato", parent=estilos["BodyText"],
        fontName="Helvetica", fontSize=9.5, leading=14, spaceAfter=7,
    )
    documento = SimpleDocTemplate(
        arquivo, pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=18 * mm, bottomMargin=18 * mm,
        title=f"Contrato Clubbar - {contrato.versao}",
    )
    historia = [
        Paragraph("CLUBBAR — CONTRATO DE PARCERIA", titulo),
        Paragraph(f"Versão {escape(contrato.versao)}", estilos["Normal"]),
        Spacer(1, 5 * mm),
    ]
    for bloco in (contrato.conteudocontrato or "").split("\n"):
        texto = escape(bloco.strip())
        historia.append(Paragraph(texto or "&nbsp;", corpo))
    documento.build(historia)
    arquivo.seek(0)
    nome = f"contrato-clubbar-{leadestabelecimentocontrato_id}.pdf"
    return StreamingResponse(
        arquivo, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


def _out(item: LeadEstabelecimentoContrato) -> dict:
    return {
        "leadestabelecimentocontrato_id": item.leadestabelecimentocontrato_id,
        "leadestabelecimento_id": item.leadestabelecimento_id,
        "contratopadrao_id": item.contratopadrao_id,
        "versao": item.versao,
        "status": item.status,
        "vrtaxaprod": float(item.vrtaxaprod),
        "vrtaxaing": float(item.vrtaxaing),
        "vrimplantacao": float(item.vrimplantacao),
        "tipopessoa": item.tipopessoa,
        "cpfcnpjcontratante": item.cpfcnpjcontratante,
        "nmrazaosocial": item.nmrazaosocial,
        "cepcontratante": item.cepcontratante,
        "enderecocontratante": item.enderecocontratante,
        "numerocontratante": item.numerocontratante,
        "complementocontratante": item.complementocontratante,
        "bairrocontratante": item.bairrocontratante,
        "estado_id_contratante": item.estado_id_contratante,
        "cidade_id_contratante": item.cidade_id_contratante,
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
    nome_contratante: str,
    cpfcnpj_contratante: str,
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
        "{{NOME_ESTABELECIMENTO}}": nome_contratante,
        "{{CPF_CNPJ}}": cpfcnpj_contratante,
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
) -> tuple[LeadEstabelecimento, ContratoPadrao, str, str, str]:
    estabelecimento = db.query(LeadEstabelecimento).filter(
        LeadEstabelecimento.leadestabelecimento_id == leadestabelecimento_id
    ).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado.")
    cpfcnpj = "".join(caractere for caractere in dados.cpfcnpj if caractere.isdigit())
    if len(cpfcnpj) not in (11, 14):
        raise HTTPException(422, "Informe um CPF ou CNPJ válido para o contrato")
    razao_social = dados.nmrazaosocial.strip()
    if len(cpfcnpj) == 14 and not razao_social:
        raise HTTPException(422, "A razão social é obrigatória para contrato com CNPJ")
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
        razao_social,
        cpfcnpj,
    ), cpfcnpj, razao_social


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
    _, _, conteudo, _, _ = _contexto_contrato(db, leadestabelecimento_id, dados)
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
    estabelecimento, modelo, conteudo, cpfcnpj, razao_social = _contexto_contrato(
        db, leadestabelecimento_id, dados
    )
    contrato_aceito = db.query(LeadEstabelecimentoContrato).filter(
        LeadEstabelecimentoContrato.leadestabelecimento_id == leadestabelecimento_id,
        LeadEstabelecimentoContrato.status == "ACEITO",
    ).first()
    if estabelecimento.status in (
        StatusLeadEstabelecimento.ACEITOU_PARCERIA,
        StatusLeadEstabelecimento.CONVERTIDO,
    ) or contrato_aceito:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "O contrato deste estabelecimento já foi aceito e não pode ser "
                "substituído. Uma alteração futura deverá ser feita por aditivo."
            ),
        )
    item = LeadEstabelecimentoContrato(
        leadestabelecimento_id=leadestabelecimento_id,
        contratopadrao_id=modelo.contratopadrao_id,
        status="ENVIADO",
        versao=modelo.versao,
        vrtaxaprod=dados.vrtaxaprod,
        vrtaxaing=dados.vrtaxaing,
        vrimplantacao=modelo.vrimplantacao,
        tipopessoa="PJ" if len(cpfcnpj) == 14 else "PF",
        cpfcnpjcontratante=cpfcnpj,
        nmrazaosocial=razao_social,
        cepcontratante=estabelecimento.cep,
        enderecocontratante=estabelecimento.endereco,
        numerocontratante=estabelecimento.numero,
        complementocontratante=estabelecimento.complemento,
        bairrocontratante=estabelecimento.bairro,
        estado_id_contratante=estabelecimento.estado_id,
        cidade_id_contratante=estabelecimento.cidade_id,
        conteudocontrato=conteudo,
        hashdocumento=sha256(conteudo.encode("utf-8")).hexdigest(),
        dtdisponibilizacao=datetime.now(),
    )
    estabelecimento.vrtaxaprod = dados.vrtaxaprod
    estabelecimento.vrtaxaing = dados.vrtaxaing
    db.add(item)
    db.add(
        LeadMensagem(
            leadparceiro_id=estabelecimento.leadparceiro_id,
            leadestabelecimento_id=leadestabelecimento_id,
            origem="CLUBBAR",
            mensagem="Contrato enviado.",
            lida="N",
        )
    )
    db.commit()
    db.refresh(item)
    return _out(item)


@portal_router.patch("/contratos/{leadestabelecimentocontrato_id}/aceitar")
async def aceitar_contrato(
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
    if item.status != "ACEITO":
        item.status = "ACEITO"
        item.nmsignatario = lead.nmresponsavel
        item.ipaceite = request.client.host if request.client else None
        item.dtaceite = datetime.now()
        db.commit()
        db.refresh(item)
    return _out(item)


@portal_router.get("/contratos/{leadestabelecimentocontrato_id}/implantacao")
async def consultar_implantacao_portal(
    leadestabelecimentocontrato_id: int,
    lead: LeadParceiro = Depends(obter_lead_portal),
    db: Session = Depends(get_db),
):
    contrato = db.query(LeadEstabelecimentoContrato).join(LeadEstabelecimento).filter(
        LeadEstabelecimentoContrato.leadestabelecimentocontrato_id == leadestabelecimentocontrato_id,
        LeadEstabelecimento.leadparceiro_id == lead.leadparceiro_id,
    ).first()
    if not contrato or contrato.status != "ACEITO":
        raise HTTPException(404, "Contrato aceito não encontrado")
    cobranca = db.query(CobrancaImplantacao).filter(
        CobrancaImplantacao.leadestabelecimentocontrato_id == leadestabelecimentocontrato_id
    ).first()
    if not cobranca or cobranca.status == "VENCIDA":
        cobranca = await criar_cobranca_implantacao(db, contrato)
    cobranca = await reconciliar_cobranca_implantacao(db, cobranca)
    return saida_cobranca(cobranca)


@router.get("/estabelecimento/{leadestabelecimento_id}/implantacao")
async def consultar_implantacao_admin(
    leadestabelecimento_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    cobranca = db.query(CobrancaImplantacao).filter(
        CobrancaImplantacao.leadestabelecimento_id == leadestabelecimento_id
    ).order_by(CobrancaImplantacao.cobrancaimplantacao_id.desc()).first()
    if not cobranca:
        raise HTTPException(404, "Cobrança de implantação ainda não gerada")
    cobranca = await reconciliar_cobranca_implantacao(db, cobranca)
    return saida_cobranca(cobranca)


@router.patch("/implantacao/{cobrancaimplantacao_id}/isentar")
def isentar_implantacao(
    cobrancaimplantacao_id: int,
    dados: IsencaoImplantacaoIn,
    operador: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    cobranca = db.query(CobrancaImplantacao).filter(
        CobrancaImplantacao.cobrancaimplantacao_id == cobrancaimplantacao_id
    ).with_for_update().first()
    if not cobranca:
        raise HTTPException(404, "Cobrança de implantação não encontrada")
    if cobranca.status == "PAGA":
        raise HTTPException(409, "Uma implantação paga não pode ser isentada")
    cobranca.status = "ISENTA"
    cobranca.justificativaisencao = dados.justificativa.strip()
    cobranca.operadorisencao_id = int(operador.get("sub") or 0) or None
    cobranca.dtisencao = datetime.now()
    db.commit()
    db.refresh(cobranca)
    return saida_cobranca(cobranca)
