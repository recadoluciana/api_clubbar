from datetime import datetime
from html import escape
from io import BytesIO
from hashlib import sha256
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.services.contrato_automatico import _gerar_conteudo, campos_endereco_pendentes, endereco_contrato, preencher_contrato_portal
from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.contratolead import LeadEstabelecimentoContrato
from app.models.contratopadrao import ContratoPadrao
from app.models.taxapadrao import TaxaPadrao
from app.services.taxa_service import taxa_padrao_vigente
from app.models.leadestabelecimento import LeadEstabelecimento, StatusLeadEstabelecimento
from app.models.leadmensagem import LeadMensagem
from app.models.leadparceiro import LeadParceiro
from app.models.loja import Loja
from app.models.cobrancaimplantacao import CobrancaImplantacao
from app.services.portal_acesso_service import obter_lead_portal
from app.services.implantacao_service import criar_cobranca_implantacao, reconciliar_cobranca_implantacao, saida_cobranca
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from app.utils.documento import normalizar_cpf_cnpj


router = APIRouter(prefix="/lead-estabelecimento-contratos", tags=["Contratos de estabelecimentos de leads"])
portal_router = APIRouter(prefix="/portal-parceiro", tags=["Portal do parceiro"])


class LeadEstabelecimentoContratoCreate(BaseModel):
    versao: str | None = Field(default=None, max_length=30)
    vrtaxaprod: float | None = Field(default=None, ge=0, le=100)
    vrtaxaing: float | None = Field(default=None, ge=0, le=100)
    cpfcnpj: str = Field(min_length=11, max_length=18)
    nmrazaosocial: str = Field(min_length=2, max_length=160)


class IsencaoImplantacaoIn(BaseModel):
    justificativa: str = Field(min_length=10, max_length=500)


def _resposta_pdf_contrato(contrato: LeadEstabelecimentoContrato) -> StreamingResponse:
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
    nome = f"contrato-clubbar-{contrato.leadestabelecimentocontrato_id}.pdf"
    return StreamingResponse(
        arquivo, media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


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
    return _resposta_pdf_contrato(contrato)


@router.get("/{leadestabelecimentocontrato_id}/pdf")
def contrato_pdf_admin(
    leadestabelecimentocontrato_id: int,
    _: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    contrato = db.get(
        LeadEstabelecimentoContrato, leadestabelecimentocontrato_id
    )
    if not contrato:
        raise HTTPException(404, "Contrato não encontrado")
    if contrato.status != "ACEITO":
        raise HTTPException(409, "Somente instrumentos assinados podem ser baixados")
    return _resposta_pdf_contrato(contrato)


def _out(item: LeadEstabelecimentoContrato) -> dict:
    return {
        "leadestabelecimentocontrato_id": item.leadestabelecimentocontrato_id,
        "tipoinstrumento": item.tipoinstrumento or "ORIGINAL",
        "contratoorigem_id": item.contratoorigem_id,
        "nrretificacao": item.nrretificacao,
        "dsjustificativa": item.dsjustificativa,
        "leadestabelecimento_id": item.leadestabelecimento_id,
        "contratopadrao_id": item.contratopadrao_id,
        "taxapadrao_id": item.taxapadrao_id,
        "versao": item.versao,
        "status": item.status,
        "vrtaxaprod": float(item.vrtaxaprod),
        "vrtaxaing": float(item.vrtaxaing),
        "vrtaxaminimaingresso": float(item.vrtaxaminimaingresso),
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


def _contexto_contrato(
    db: Session,
    leadestabelecimento_id: int,
    dados: LeadEstabelecimentoContratoCreate,
) -> tuple[LeadEstabelecimento, ContratoPadrao, TaxaPadrao, str, str, str, float, float]:
    estabelecimento = db.query(LeadEstabelecimento).filter(
        LeadEstabelecimento.leadestabelecimento_id == leadestabelecimento_id
    ).first()
    if not estabelecimento:
        raise HTTPException(status_code=404, detail="Estabelecimento não encontrado.")
    try:
        cpfcnpj = normalizar_cpf_cnpj(dados.cpfcnpj)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
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
    taxa = taxa_padrao_vigente(db)
    # O contrato sempre congela a versão vigente; valores enviados pela tela não podem
    # alterar silenciosamente a política comercial versionada.
    taxa_produtos = float(taxa.pctaxaproduto)
    taxa_ingressos = float(taxa.pctaxaingresso)
    taxa_minima = float(taxa.vrtaxaminimaingresso)
    return estabelecimento, modelo, taxa, _gerar_conteudo(
        estabelecimento,
        lead,
        cidade,
        estado,
        modelo.versao,
        taxa_produtos,
        taxa_ingressos,
        taxa_minima,
        modelo,
        razao_social,
        cpfcnpj,
    ), cpfcnpj, razao_social, taxa_produtos, taxa_ingressos


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
    _, _, _, conteudo, _, _, _, _ = _contexto_contrato(db, leadestabelecimento_id, dados)
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
    estabelecimento, modelo, taxa, conteudo, cpfcnpj, razao_social, taxa_produtos, taxa_ingressos = _contexto_contrato(
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
        taxapadrao_id=taxa.taxapadrao_id,
        status="ENVIADO",
        versao=modelo.versao,
        vrtaxaprod=taxa_produtos,
        vrtaxaing=taxa_ingressos,
        vrtaxaminimaingresso=taxa.vrtaxaminimaingresso,
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
    estabelecimento.vrtaxaprod = taxa_produtos
    estabelecimento.vrtaxaing = taxa_ingressos
    estabelecimento.vrtaxaminimaingresso = taxa.vrtaxaminimaingresso
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


class RetificacaoContratoIn(BaseModel):
    motivo: str = Field(min_length=10, max_length=500)
    cpfcnpj: str = Field(min_length=11, max_length=18)
    nmrazaosocial: str = Field(min_length=2, max_length=160)
    cep: str = Field(pattern=r"^\d{8}$")
    endereco: str = Field(min_length=1, max_length=255)
    numero: str = Field(min_length=1, max_length=20)
    bairro: str = Field(min_length=1, max_length=120)
    complemento: str | None = Field(default=None, max_length=120)
    estado_id: int = Field(gt=0)
    cidade_id: int = Field(gt=0)
    vrtaxaprod: Decimal = Field(ge=0, le=100, max_digits=10, decimal_places=2)
    vrtaxaing: Decimal = Field(ge=0, le=100, max_digits=10, decimal_places=2)
    vrtaxaminimaingresso: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    confirma_mesma_parte: bool = False


def _preparar_retificacao(db: Session, estabelecimento_id: int, dados: RetificacaoContratoIn):
    estabelecimento = db.get(LeadEstabelecimento, estabelecimento_id)
    if estabelecimento is None:
        raise HTTPException(404, "Estabelecimento não encontrado.")
    original = db.query(LeadEstabelecimentoContrato).filter(
        LeadEstabelecimentoContrato.leadestabelecimento_id == estabelecimento_id,
        LeadEstabelecimentoContrato.tipoinstrumento == "ORIGINAL",
        LeadEstabelecimentoContrato.status == "ACEITO",
    ).order_by(LeadEstabelecimentoContrato.leadestabelecimentocontrato_id.desc()).first()
    if original is None:
        raise HTTPException(409, "É necessário um contrato original aceito para emitir uma retificação.")
    pendente = db.query(LeadEstabelecimentoContrato).filter(
        LeadEstabelecimentoContrato.contratoorigem_id == original.leadestabelecimentocontrato_id,
        LeadEstabelecimentoContrato.status == "ENVIADO",
    ).first()
    if pendente is not None:
        raise HTTPException(409, "Já existe uma retificação aguardando assinatura. Cancele-a antes de emitir outra.")
    anterior = db.query(LeadEstabelecimentoContrato).filter(
        LeadEstabelecimentoContrato.contratoorigem_id == original.leadestabelecimentocontrato_id,
        LeadEstabelecimentoContrato.status == "ACEITO",
    ).order_by(LeadEstabelecimentoContrato.nrretificacao.desc()).first() or original
    cidade = db.get(Cidade, dados.cidade_id)
    estado = db.get(Estado, dados.estado_id)
    if cidade is None or estado is None or cidade.estado_id != estado.estado_id:
        raise HTTPException(422, "Cidade e estado informados são incompatíveis.")
    try:
        documento = normalizar_cpf_cnpj(dados.cpfcnpj)
        anterior_documento = normalizar_cpf_cnpj(anterior.cpfcnpjcontratante)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if anterior_documento != documento:
        if estabelecimento.status == StatusLeadEstabelecimento.CONVERTIDO:
            raise HTTPException(409, "Após a conversão, a correção do CPF/CNPJ exige revisão do cadastro financeiro da empresa.")
        if len(anterior_documento) != len(documento):
            raise HTTPException(422, "A mudança entre CPF e CNPJ exige novo contrato, não retificação.")
        if not dados.confirma_mesma_parte:
            raise HTTPException(422, "Confirme que o CPF/CNPJ corrigido pertence à mesma parte contratante.")
    if not all((valor or "").strip() for valor in (dados.endereco, dados.numero, dados.bairro, dados.nmrazaosocial, dados.motivo)):
        raise HTTPException(422, "Preencha os dados corrigidos e a justificativa.")
    numero = db.query(LeadEstabelecimentoContrato.nrretificacao).filter(
        LeadEstabelecimentoContrato.contratoorigem_id == original.leadestabelecimentocontrato_id,
    ).order_by(LeadEstabelecimentoContrato.nrretificacao.desc()).first()
    nrretificacao = int(numero[0] or 0) + 1 if numero else 1
    complemento = f", {dados.complemento.strip()}" if dados.complemento and dados.complemento.strip() else ""
    endereco_novo = f"{dados.endereco.strip()}, {dados.numero.strip()}{complemento}, bairro {dados.bairro.strip()}, {cidade.nmcidade}/{estado.sgestado}, CEP {dados.cep}"
    alteracoes = []
    def registrar(rotulo, antigo, novo):
        if str(antigo or "").strip() != str(novo or "").strip():
            alteracoes.append(f"{rotulo}: de '{antigo or 'não informado'}' para '{novo}'.")
    registrar("CPF/CNPJ", anterior.cpfcnpjcontratante, documento)
    registrar("Nome ou razão social", anterior.nmrazaosocial, dados.nmrazaosocial.strip())
    anterior_endereco = f"{anterior.enderecocontratante or 'não informado'}, {anterior.numerocontratante or 'não informado'}, bairro {anterior.bairrocontratante or 'não informado'}, CEP {anterior.cepcontratante or 'não informado'}"
    if (anterior.cepcontratante, anterior.enderecocontratante, anterior.numerocontratante, anterior.bairrocontratante, anterior.complementocontratante, anterior.estado_id_contratante, anterior.cidade_id_contratante) != (dados.cep, dados.endereco.strip(), dados.numero.strip(), dados.bairro.strip(), (dados.complemento or "").strip() or None, dados.estado_id, dados.cidade_id):
        alteracoes.append(f"Endereço: de '{anterior_endereco}' para '{endereco_novo}'.")
    registrar("Taxa de produtos", f"{Decimal(anterior.vrtaxaprod):.2f}%", f"{dados.vrtaxaprod:.2f}%")
    registrar("Taxa de ingressos", f"{Decimal(anterior.vrtaxaing):.2f}%", f"{dados.vrtaxaing:.2f}%")
    registrar("Valor mínimo cobrado por ingresso", f"R$ {Decimal(anterior.vrtaxaminimaingresso):.2f}", f"R$ {dados.vrtaxaminimaingresso:.2f}")
    if not alteracoes:
        raise HTTPException(422, "Nenhum dado foi alterado em relação ao instrumento vigente.")
    texto = (
        f"{nrretificacao}º TERMO DE RETIFICAÇÃO E RATIFICAÇÃO DO CONTRATO CLUBBAR\n"
        f"Contrato original nº {original.leadestabelecimentocontrato_id}, aceito em {original.dtaceite.strftime('%d/%m/%Y %H:%M') if original.dtaceite else 'data não registrada'} e identificado pelo hash {original.hashdocumento or 'não registrado'}.\n"
        f"Estabelecimento: {estabelecimento.nmestabelecimento}.\n"
        f"Justificativa: {dados.motivo.strip()}\n"
        "As partes retificam os dados abaixo, com efeitos a partir do aceite deste termo:\n"
        + "\n".join(f"- {linha}" for linha in alteracoes)
        + "\nPermanecem ratificadas as demais cláusulas e condições do contrato original e dos termos anteriores que não forem incompatíveis com esta retificação."
    )
    return original, anterior, nrretificacao, documento, texto


@router.post("/estabelecimento/{leadestabelecimento_id}/retificacoes/previsualizar")
def previsualizar_retificacao(leadestabelecimento_id: int, dados: RetificacaoContratoIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    _, _, numero, _, texto = _preparar_retificacao(db, leadestabelecimento_id, dados)
    return {"nrretificacao": numero, "conteudocontrato": texto}


@router.post("/estabelecimento/{leadestabelecimento_id}/retificacoes", status_code=201)
def criar_retificacao(leadestabelecimento_id: int, dados: RetificacaoContratoIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    original, _, numero, documento, texto = _preparar_retificacao(db, leadestabelecimento_id, dados)
    item = LeadEstabelecimentoContrato(
        tipoinstrumento="RETIFICACAO", contratoorigem_id=original.leadestabelecimentocontrato_id,
        nrretificacao=numero, dsjustificativa=dados.motivo.strip(),
        mesmaparteconfirmada="S" if dados.confirma_mesma_parte else "N",
        leadestabelecimento_id=leadestabelecimento_id, contratopadrao_id=original.contratopadrao_id,
        taxapadrao_id=original.taxapadrao_id, status="ENVIADO", versao=original.versao,
        vrtaxaprod=dados.vrtaxaprod, vrtaxaing=dados.vrtaxaing,
        vrtaxaminimaingresso=dados.vrtaxaminimaingresso, vrimplantacao=original.vrimplantacao,
        tipopessoa="PJ" if len(documento) == 14 else "PF", cpfcnpjcontratante=documento,
        nmrazaosocial=dados.nmrazaosocial.strip(), cepcontratante=dados.cep,
        enderecocontratante=dados.endereco.strip(), numerocontratante=dados.numero.strip(),
        bairrocontratante=dados.bairro.strip(), complementocontratante=(dados.complemento or "").strip() or None,
        estado_id_contratante=dados.estado_id, cidade_id_contratante=dados.cidade_id,
        conteudocontrato=texto, hashdocumento=sha256(texto.encode("utf-8")).hexdigest(),
        dtdisponibilizacao=datetime.now(),
    )
    db.add(item)
    db.add(LeadMensagem(
        leadparceiro_id=db.get(LeadEstabelecimento, leadestabelecimento_id).leadparceiro_id,
        leadestabelecimento_id=leadestabelecimento_id, origem="CLUBBAR",
        mensagem=f"Retificação nº {numero} do contrato disponível para revisão e assinatura.", lida="N",
    ))
    db.commit()
    db.refresh(item)
    return _out(item)


@router.patch("/retificacoes/{retificacao_id}/cancelar")
def cancelar_retificacao(retificacao_id: int, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.get(LeadEstabelecimentoContrato, retificacao_id)
    if item is None or item.tipoinstrumento != "RETIFICACAO":
        raise HTTPException(404, "Retificação não encontrada.")
    if item.status != "ENVIADO":
        raise HTTPException(409, "Somente uma retificação pendente pode ser cancelada.")
    item.status = "CANCELADO"
    db.commit()
    return _out(item)


class DadosContratoPortal(BaseModel):
    cpfcnpj: str = Field(min_length=11, max_length=18)
    nmrazaosocial: str = Field(min_length=2, max_length=160)


class EnderecoContratoPortal(BaseModel):
    cep: str = Field(pattern=r"^\d{8}$")
    endereco: str = Field(min_length=1, max_length=255)
    numero: str = Field(min_length=1, max_length=20)
    bairro: str = Field(min_length=1, max_length=120)
    complemento: str | None = Field(default=None, max_length=120)
    estado_id: int = Field(gt=0)
    cidade_id: int = Field(gt=0)


@portal_router.patch("/contratos/{contrato_id}/dados")
def salvar_dados_contrato_portal(
    contrato_id: int, dados: DadosContratoPortal,
    lead: LeadParceiro = Depends(obter_lead_portal), db: Session = Depends(get_db),
):
    return _out(preencher_contrato_portal(db, lead.leadparceiro_id, contrato_id, dados.cpfcnpj, dados.nmrazaosocial))


@portal_router.patch("/contratos/{contrato_id}/endereco")
def atualizar_endereco_contrato_portal(
    contrato_id: int, dados: EnderecoContratoPortal,
    lead: LeadParceiro = Depends(obter_lead_portal), db: Session = Depends(get_db),
):
    item = db.query(LeadEstabelecimentoContrato).join(LeadEstabelecimento).filter(
        LeadEstabelecimentoContrato.leadestabelecimentocontrato_id == contrato_id,
        LeadEstabelecimento.leadparceiro_id == lead.leadparceiro_id,
    ).with_for_update().first()
    if item is None:
        raise HTTPException(404, "Contrato não encontrado.")
    if item.status not in ("RASCUNHO", "ENVIADO"):
        raise HTTPException(409, "O endereço de um contrato aceito não pode ser alterado.")
    if item.tipoinstrumento == "RETIFICACAO":
        raise HTTPException(409, "Peça à equipe Clubbar a correção e reemissão do termo de retificação.")
    estabelecimento = db.get(LeadEstabelecimento, item.leadestabelecimento_id)
    cidade = db.get(Cidade, dados.cidade_id)
    estado = db.get(Estado, dados.estado_id)
    if cidade is None or estado is None or cidade.estado_id != estado.estado_id:
        raise HTTPException(422, "Selecione uma cidade e um estado compatíveis.")
    if not all((valor or "").strip() for valor in (dados.endereco, dados.numero, dados.bairro)):
        raise HTTPException(422, "Informe endereço, número e bairro do estabelecimento.")
    cidade_antiga = db.get(Cidade, estabelecimento.cidade_id) if estabelecimento.cidade_id else None
    estado_antigo = db.get(Estado, estabelecimento.estado_id) if estabelecimento.estado_id else None
    endereco_antigo = endereco_contrato(estabelecimento, cidade_antiga, estado_antigo)
    if endereco_antigo not in item.conteudocontrato:
        raise HTTPException(409, "O endereço não foi localizado no texto do contrato. Solicite à equipe Clubbar um novo contrato antes de assinar.")
    estabelecimento.cep = dados.cep
    estabelecimento.endereco = dados.endereco.strip()
    estabelecimento.numero = dados.numero.strip()
    estabelecimento.bairro = dados.bairro.strip()
    estabelecimento.complemento = (dados.complemento or "").strip() or None
    estabelecimento.estado_id = dados.estado_id
    estabelecimento.cidade_id = dados.cidade_id
    item.cepcontratante = estabelecimento.cep
    item.enderecocontratante = estabelecimento.endereco
    item.numerocontratante = estabelecimento.numero
    item.bairrocontratante = estabelecimento.bairro
    item.complementocontratante = estabelecimento.complemento
    item.estado_id_contratante = estabelecimento.estado_id
    item.cidade_id_contratante = estabelecimento.cidade_id
    item.conteudocontrato = item.conteudocontrato.replace(
        endereco_antigo, endereco_contrato(estabelecimento, cidade, estado)
    )
    item.hashdocumento = sha256(item.conteudocontrato.encode("utf-8")).hexdigest()
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
        .with_for_update()
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")
    if item.status == "RASCUNHO":
        raise HTTPException(422, "Preencha os dados do contrato antes de assinar.")
    if item.status not in ("ENVIADO", "ACEITO"):
        raise HTTPException(409, "Este instrumento não está disponível para assinatura.")
    if item.status != "ACEITO":
        estabelecimento = db.get(LeadEstabelecimento, item.leadestabelecimento_id)
        if item.tipoinstrumento == "RETIFICACAO":
            origem = db.get(LeadEstabelecimentoContrato, item.contratoorigem_id)
            if origem is None or origem.status != "ACEITO" or origem.leadestabelecimento_id != item.leadestabelecimento_id:
                raise HTTPException(409, "Contrato original aceito não encontrado para esta retificação.")
            cidade = db.get(Cidade, item.cidade_id_contratante)
            estado = db.get(Estado, item.estado_id_contratante)
            if (len("".join(c for c in (item.cepcontratante or "") if c.isdigit())) != 8
                or not all((v or "").strip() for v in (item.enderecocontratante, item.numerocontratante, item.bairrocontratante, item.nmrazaosocial))
                or cidade is None or estado is None or cidade.estado_id != estado.estado_id):
                raise HTTPException(422, "O termo de retificação contém dados obrigatórios incompletos.")
            if item.hashdocumento != sha256(item.conteudocontrato.encode("utf-8")).hexdigest():
                raise HTTPException(409, "A integridade do termo de retificação não confere.")
            estabelecimento.cpfcnpj = item.cpfcnpjcontratante
            estabelecimento.cep = item.cepcontratante
            estabelecimento.endereco = item.enderecocontratante
            estabelecimento.numero = item.numerocontratante
            estabelecimento.bairro = item.bairrocontratante
            estabelecimento.complemento = item.complementocontratante
            estabelecimento.estado_id = item.estado_id_contratante
            estabelecimento.cidade_id = item.cidade_id_contratante
            estabelecimento.vrtaxaprod = item.vrtaxaprod
            estabelecimento.vrtaxaing = item.vrtaxaing
            estabelecimento.vrtaxaminimaingresso = item.vrtaxaminimaingresso
            loja = db.query(Loja).filter(Loja.leadestabelecimento_id == estabelecimento.leadestabelecimento_id).first()
            if loja is not None:
                loja.endloja = item.enderecocontratante
                loja.nrendeloja = item.numerocontratante
                loja.nrceploja = item.cepcontratante
                loja.dsbairroloja = item.bairrocontratante
                loja.complementoloja = item.complementocontratante
                loja.estado_id = item.estado_id_contratante
                loja.cidade_id = item.cidade_id_contratante
                loja.vrtaxaprod = item.vrtaxaprod
                loja.vrtaxaing = item.vrtaxaing
                loja.vrtaxaminimaingresso = item.vrtaxaminimaingresso
        else:
            pendentes = campos_endereco_pendentes(estabelecimento)
            if pendentes:
                raise HTTPException(422, "Complete o endereço do estabelecimento antes de assinar: " + ", ".join(pendentes) + ".")
            cidade = db.get(Cidade, estabelecimento.cidade_id)
            estado = db.get(Estado, estabelecimento.estado_id)
            if cidade is None or estado is None or cidade.estado_id != estado.estado_id:
                raise HTTPException(422, "Corrija a cidade e o estado do estabelecimento antes de assinar.")
            if (
                item.cepcontratante != estabelecimento.cep
                or item.enderecocontratante != estabelecimento.endereco
                or item.numerocontratante != estabelecimento.numero
                or item.bairrocontratante != estabelecimento.bairro
                or item.estado_id_contratante != estabelecimento.estado_id
                or item.cidade_id_contratante != estabelecimento.cidade_id
                or endereco_contrato(estabelecimento, cidade, estado) not in item.conteudocontrato
            ):
                raise HTTPException(422, "O endereço do contrato precisa ser atualizado antes da assinatura.")
            estabelecimento.vrtaxaprod = item.vrtaxaprod
            estabelecimento.vrtaxaing = item.vrtaxaing
            estabelecimento.vrtaxaminimaingresso = item.vrtaxaminimaingresso
        item.status = "ACEITO"
        item.nmsignatario = lead.nmresponsavel
        item.cpfcnpjsignatario = item.cpfcnpjcontratante
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
    if contrato.tipoinstrumento == "RETIFICACAO":
        contrato = db.get(LeadEstabelecimentoContrato, contrato.contratoorigem_id)
        if contrato is None or contrato.status != "ACEITO":
            raise HTTPException(409, "Contrato original aceito não encontrado.")
    cobranca = db.query(CobrancaImplantacao).filter(
        CobrancaImplantacao.leadestabelecimentocontrato_id == contrato.leadestabelecimentocontrato_id
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
