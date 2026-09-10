from datetime import datetime
from hashlib import sha256
from fastapi import HTTPException
from app.models.cidade import Cidade
from app.models.estado import Estado
from app.models.contratolead import LeadEstabelecimentoContrato
from app.models.contratopadrao import ContratoPadrao
from app.models.leadestabelecimento import LeadEstabelecimento, StatusLeadEstabelecimento
from app.models.leadparceiro import LeadParceiro
from app.services.taxa_service import taxa_padrao_vigente

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
    taxa_minima_ingresso: float,
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
        "{{TAXA_MINIMA_INGRESSO}}": f"{taxa_minima_ingresso:.2f}",
        "{{TAXA_IMPLANTACAO}}": f"{float(modelo.vrimplantacao):.2f}",
    }
    conteudo = modelo.conteudomodelo
    if "{{TAXA_MINIMA_INGRESSO}}" not in conteudo:
        conteudo += (
            "\n- Regra da taxa de conveniência: {{TAXA_INGRESSOS}}% por ingresso "
            "ou o mínimo de R$ {{TAXA_MINIMA_INGRESSO}}, prevalecendo o maior valor."
        )
    for marcador, valor in valores.items():
        conteudo = conteudo.replace(marcador, valor)
    return conteudo.strip()


def garantir_contrato(db, estabelecimento):
    # Serializes automatic creation against concurrent requests for the same establishment.
    estabelecimento = db.query(LeadEstabelecimento).filter(
        LeadEstabelecimento.leadestabelecimento_id == estabelecimento.leadestabelecimento_id
    ).with_for_update().one()
    existente = db.query(LeadEstabelecimentoContrato).filter(
        LeadEstabelecimentoContrato.leadestabelecimento_id == estabelecimento.leadestabelecimento_id
    ).order_by(LeadEstabelecimentoContrato.leadestabelecimentocontrato_id.desc()).first()
    if existente:
        return existente
    if estabelecimento.status in (StatusLeadEstabelecimento.CONVERTIDO, StatusLeadEstabelecimento.ACEITOU_PARCERIA):
        return None
    modelo = db.query(ContratoPadrao).filter(ContratoPadrao.sitcontrato == "ATIVO").order_by(
        ContratoPadrao.contratopadrao_id.desc()).first()
    if not modelo:
        raise HTTPException(422, "Nenhum contrato padrão ativo está disponível.")
    taxa = taxa_padrao_vigente(db)
    lead = db.get(LeadParceiro, estabelecimento.leadparceiro_id)
    documento = "".join(c for c in (estabelecimento.cpfcnpj or "") if c.isdigit())
    item = LeadEstabelecimentoContrato(
        leadestabelecimento_id=estabelecimento.leadestabelecimento_id,
        contratopadrao_id=modelo.contratopadrao_id, taxapadrao_id=taxa.taxapadrao_id,
        status="RASCUNHO", versao=modelo.versao,
        vrtaxaprod=taxa.pctaxaproduto, vrtaxaing=taxa.pctaxaingresso,
        vrtaxaminimaingresso=taxa.vrtaxaminimaingresso, vrimplantacao=modelo.vrimplantacao,
        cpfcnpjcontratante=documento or None,
        nmrazaosocial=estabelecimento.nmestabelecimento,
        cepcontratante=estabelecimento.cep, enderecocontratante=estabelecimento.endereco,
        numerocontratante=estabelecimento.numero, complementocontratante=estabelecimento.complemento,
        bairrocontratante=estabelecimento.bairro, estado_id_contratante=estabelecimento.estado_id,
        cidade_id_contratante=estabelecimento.cidade_id,
        dtdisponibilizacao=datetime.now(),
    )
    item.conteudocontrato = _gerar_conteudo(
        estabelecimento, lead, db.get(Cidade, estabelecimento.cidade_id),
        db.get(Estado, estabelecimento.estado_id), modelo.versao,
        float(item.vrtaxaprod), float(item.vrtaxaing), float(item.vrtaxaminimaingresso), modelo,
        "[Nome completo ou razão social a preencher]", "[CPF/CNPJ a preencher]",
    )
    item.hashdocumento = sha256(item.conteudocontrato.encode("utf-8")).hexdigest()
    db.add(item)
    db.flush()
    return item


def preencher_contrato_portal(db, lead_id, contrato_id, documento, nome):
    item = db.query(LeadEstabelecimentoContrato).join(LeadEstabelecimento).filter(
        LeadEstabelecimentoContrato.leadestabelecimentocontrato_id == contrato_id,
        LeadEstabelecimento.leadparceiro_id == lead_id,
    ).with_for_update().first()
    if not item:
        raise HTTPException(404, "Contrato não encontrado.")
    if item.status != "RASCUNHO":
        raise HTTPException(409, "Este contrato já foi finalizado e não pode ser alterado pelo portal.")
    documento = "".join(c for c in documento if c.isdigit())
    nome = nome.strip()
    if len(documento) not in (11, 14) or len(nome) < 2:
        raise HTTPException(422, "Informe CPF/CNPJ e nome completo ou razão social.")
    # Replace only the draft identity, preserving its original clauses and negotiated values.
    import re
    replacements = {
        "[Nome completo ou razão social a preencher]": nome,
        "[CPF/CNPJ a preencher]": documento,
    }
    pattern = "|".join(re.escape(value) for value in replacements)
    item.conteudocontrato = re.sub(pattern, lambda match: replacements[match.group()], item.conteudocontrato)
    item.nmrazaosocial = nome
    item.cpfcnpjcontratante = documento
    item.tipopessoa = "PJ" if len(documento) == 14 else "PF"
    item.status = "ENVIADO"
    item.hashdocumento = sha256(item.conteudocontrato.encode("utf-8")).hexdigest()
    db.commit()
    db.refresh(item)
    return item
