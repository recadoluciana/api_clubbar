from datetime import date, datetime
from decimal import Decimal
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, exists
from sqlalchemy.orm import Session

from app.core.config import APP_ENV, ASAAS_API_KEY, MERCADO_PAGO_API_BASE_URL
from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial
from app.core.permissoes_loja import validar_gerenciamento_organizacao
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.loja import Loja
from app.models.checkout_asaas import CheckoutAsaas
from app.models.checkout_mercadopago import CheckoutMercadoPago
from app.models.itvenda import ItVenda
from app.models.produto import Produto
from app.models.reserva_ingresso import ReservaIngresso
from app.models.evento import Evento
from app.models.contratolead import LeadEstabelecimentoContrato
from app.services.publicacao_pendente_service import publicar_conteudos_aguardando_asaas
from app.services.titular_financeiro_service import sincronizar_integracao_asaas_da_loja, ambiente_asaas
from app.services.mercado_pago_service import obter_token_loja, buscar_pagamento_por_id, cancelar_pagamento_por_id
from app.models.titularfinanceiro import TitularFinanceiro
from app.models.lojamercadopago import LojaMercadoPago
from app.utils.documento import normalizar_cpf_cnpj


router = APIRouter(prefix="/titular-financeiro", tags=["Titular financeiro"])
ASAAS_BASE_URL = os.getenv("ASAAS_BASE_URL", "https://api-sandbox.asaas.com/v3").rstrip("/")


def _pendentes_mercado_pago(db: Session, loja_id: int):
    return db.query(CheckoutMercadoPago).filter(
        CheckoutMercadoPago.loja_id == loja_id,
        CheckoutMercadoPago.venda_id.is_(None),
        CheckoutMercadoPago.status.in_(["PENDING", "IN_PROCESS", "ACTIVE"]),
    ).order_by(CheckoutMercadoPago.dtcriacao.asc()).all()


def _saida_pendente(checkout: CheckoutMercadoPago) -> dict:
    return {
        "checkout_id": checkout.checkout_mercadopago_id,
        "payment_id": str(checkout.payment_id or ""),
        "status": checkout.status,
        "valor": float(checkout.valor or 0),
        "metodo": checkout.metodo_solicitado,
        "criado_em": checkout.dtcriacao,
    }


class TitularFinanceiroIn(BaseModel):
    organizacao_id: int = Field(gt=0)
    tipotitular: str
    cpfcnpj: str
    nmrazaosocial: str = Field(min_length=2, max_length=160)
    nmfantasia: str | None = Field(default=None, max_length=160)
    dtnascimento: date | None = None
    email: EmailStr
    telefone: str = Field(min_length=10, max_length=25)
    cep: str = Field(min_length=8, max_length=9)
    endereco: str = Field(min_length=2, max_length=255)
    numero: str = Field(min_length=1, max_length=20)
    complemento: str | None = Field(default=None, max_length=120)
    bairro: str = Field(min_length=2, max_length=120)
    cidade_id: int = Field(gt=0)
    estado_id: int = Field(gt=0)
    vrfaturamentomensal: Decimal = Field(gt=0)

    @field_validator("tipotitular")
    @classmethod
    def validar_tipo(cls, valor: str) -> str:
        tipo = valor.strip().upper()
        if tipo not in {"PF", "PJ"}:
            raise ValueError("Tipo de titular deve ser PF ou PJ")
        return tipo

    @field_validator("cpfcnpj")
    @classmethod
    def validar_documento(cls, valor: str) -> str:
        try:
            return normalizar_cpf_cnpj(valor) or ""
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("cep", "telefone")
    @classmethod
    def somente_numeros(cls, valor: str) -> str:
        return "".join(c for c in valor if c.isdigit())


class DadosAtivacaoAsaasIn(BaseModel):
    dtnascimento: date | None = None
    vrfaturamentomensal: Decimal = Field(gt=0)


def _validar_escopo(payload: dict, organizacao_id: int) -> None:
    validar_gerenciamento_organizacao(payload, organizacao_id)
    if int(payload.get("organizacao_id") or 0) != organizacao_id:
        raise HTTPException(status_code=403, detail="Organização fora do seu acesso")


def _out(titular: TitularFinanceiro) -> dict:
    return {
        campo: getattr(titular, campo)
        for campo in (
            "titularfinanceiro_id", "organizacao_id", "tipotitular", "cpfcnpj",
            "nmrazaosocial", "nmfantasia", "dtnascimento", "email", "telefone",
            "cep", "endereco", "numero", "complemento", "bairro", "cidade_id",
            "estado_id", "vrfaturamentomensal", "asaas_account_id", "asaas_wallet_id",
            "status_asaas", "sittitular", "onboarding_url", "dtultimaverificacao",
        )
    }


def _motivos_titular_em_uso(db: Session, titular: TitularFinanceiro) -> list[str]:
    """Informa vínculos operacionais que impedem a exclusão do titular.

    Contratos não entram nesta lista: o contrato pertence ao contratante e ao
    estabelecimento. O titular financeiro é uma configuração de recebimento
    da organização, não parte do instrumento contratual.
    """
    motivos: list[str] = []
    if titular.asaas_account_id or titular.asaas_wallet_id:
        motivos.append("subconta Asaas")
    if db.query(LojaMercadoPago.lojamercadopago_id).filter(
        LojaMercadoPago.titularfinanceiro_id == titular.titularfinanceiro_id,
        LojaMercadoPago.statusintegracao == "ATIVA",
    ).first():
        motivos.append("conexão Mercado Pago ativa")
    if db.query(Loja.loja_id).filter(
        Loja.organizacao_id == titular.organizacao_id,
        Loja.titularfinanceiro_id == titular.titularfinanceiro_id,
    ).first():
        motivos.append("estabelecimento associado")
    if titular.asaas_wallet_id and db.query(CheckoutAsaas.checkout_asaas_id).filter(
        CheckoutAsaas.asaas_wallet_loja == titular.asaas_wallet_id,
    ).first():
        motivos.append("checkout")
    return motivos


def _out_com_permissoes_de_exclusao(
    db: Session, titular: TitularFinanceiro
) -> dict:
    retorno = _out(titular)
    retorno["pode_excluir"] = not _motivos_titular_em_uso(db, titular)
    return retorno


@router.get("/organizacao/{organizacao_id}")
def consultar(
    organizacao_id: int,
    loja_id: int | None = None,
    titularfinanceiro_id: int | None = None,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    titular, loja = _resolver_titular(
        db,
        organizacao_id,
        payload,
        loja_id=loja_id,
        titularfinanceiro_id=titularfinanceiro_id,
        obrigatorio=False,
    )
    if not titular:
        return None
    retorno = _out_com_permissoes_de_exclusao(db, titular)
    retorno["loja_id"] = loja.loja_id if loja else None
    return retorno


@router.get("/organizacao/{organizacao_id}/todos")
def listar_titulares(
    organizacao_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    return [
        _out_com_permissoes_de_exclusao(db, item)
        for item in db.query(TitularFinanceiro)
        .filter(TitularFinanceiro.organizacao_id == organizacao_id)
        .order_by(TitularFinanceiro.titularfinanceiro_id.asc())
        .all()
    ]


@router.post("/organizacao/{organizacao_id}", status_code=201)
def criar_titular(
    organizacao_id: int,
    dados: TitularFinanceiroIn,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    if dados.organizacao_id != organizacao_id:
        raise HTTPException(status_code=422, detail="Organização divergente")
    if dados.tipotitular == "PF" and dados.dtnascimento is None:
        raise HTTPException(status_code=422, detail="Data de nascimento é obrigatória para PF")
    if db.query(TitularFinanceiro).filter(
        TitularFinanceiro.cpfcnpj == dados.cpfcnpj
    ).first():
        raise HTTPException(409, "Este CPF/CNPJ já possui um titular financeiro no Clubbar")
    titular = TitularFinanceiro(**dados.model_dump())
    db.add(titular)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "CPF/CNPJ ou conta Asaas já cadastrada") from exc
    db.refresh(titular)
    return _out(titular)


@router.patch(
    "/organizacao/{organizacao_id}/titular/{titularfinanceiro_id}/loja/{loja_id}"
)
def vincular_titular_a_loja(
    organizacao_id: int,
    titularfinanceiro_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    titular = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.titularfinanceiro_id == titularfinanceiro_id,
        TitularFinanceiro.organizacao_id == organizacao_id,
    ).first()
    loja = db.query(Loja).filter(
        Loja.loja_id == loja_id,
        Loja.organizacao_id == organizacao_id,
    ).first()
    if not titular or not loja:
        raise HTTPException(status_code=404, detail="Titular ou loja não encontrado")
    if loja.titularfinanceiro_id and loja.titularfinanceiro_id != titularfinanceiro_id:
        raise HTTPException(409, 'Altere o titular junto com o provedor na tela Recebimentos.')
    if str(titular.sittitular or "ATIVO").upper() != "ATIVO":
        raise HTTPException(422, "O titular financeiro está inativo e não pode ser vinculado à loja")
    loja.titularfinanceiro_id = titularfinanceiro_id
    sincronizar_integracao_asaas_da_loja(db, loja, titular)
    db.commit()
    return {"ok": True, "loja_id": loja_id, "titularfinanceiro_id": titularfinanceiro_id}


@router.delete(
    "/organizacao/{organizacao_id}/titular/{titularfinanceiro_id}/loja/{loja_id}"
)
def desvincular_titular_da_loja(
    organizacao_id: int,
    titularfinanceiro_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    loja = db.query(Loja).filter(
        Loja.loja_id == loja_id,
        Loja.organizacao_id == organizacao_id,
        Loja.titularfinanceiro_id == titularfinanceiro_id,
    ).first()
    if not loja:
        raise HTTPException(404, "Associação entre estabelecimento e titular não encontrada")
    loja.titularfinanceiro_id = None
    db.commit()
    return {"ok": True, "loja_id": loja_id, "titularfinanceiro_id": None}


@router.get("/organizacao/{organizacao_id}/loja/{loja_id}/pagamentos-pendentes")
def listar_pagamentos_pendentes_loja(
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    loja = db.query(Loja).filter(
        Loja.loja_id == loja_id,
        Loja.organizacao_id == organizacao_id,
    ).first()
    if not loja:
        raise HTTPException(404, "Estabelecimento não encontrado")
    return {"pagamentos": [_saida_pendente(item) for item in _pendentes_mercado_pago(db, loja_id)]}


@router.post("/organizacao/{organizacao_id}/loja/{loja_id}/pagamentos-pendentes/verificar")
async def verificar_pagamentos_pendentes_loja(
    organizacao_id: int,
    loja_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    loja = db.query(Loja).filter(
        Loja.loja_id == loja_id,
        Loja.organizacao_id == organizacao_id,
    ).first()
    if not loja:
        raise HTTPException(404, "Estabelecimento não encontrado")
    token, _ = await obter_token_loja(db, loja_id)
    verificacoes = []
    for checkout in _pendentes_mercado_pago(db, loja_id):
        if not checkout.payment_id:
            continue
        pagamento = await buscar_pagamento_por_id(
            access_token=token,
            payment_id=str(checkout.payment_id),
        )
        if pagamento and pagamento.get("status"):
            checkout.status = str(pagamento["status"]).upper()
            verificacoes.append({
                "payment_id": str(checkout.payment_id),
                "status": checkout.status,
            })
    db.commit()
    return {"pagamentos": [_saida_pendente(item) for item in _pendentes_mercado_pago(db, loja_id)], "verificados": verificacoes}


@router.post("/organizacao/{organizacao_id}/loja/{loja_id}/pagamentos-pendentes/{checkout_id}/cancelar")
async def cancelar_pagamento_pendente_loja(
    organizacao_id: int,
    loja_id: int,
    checkout_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    checkout = db.query(CheckoutMercadoPago).join(
        Loja, Loja.loja_id == CheckoutMercadoPago.loja_id
    ).filter(
        CheckoutMercadoPago.checkout_mercadopago_id == checkout_id,
        CheckoutMercadoPago.loja_id == loja_id,
        Loja.organizacao_id == organizacao_id,
        CheckoutMercadoPago.venda_id.is_(None),
        CheckoutMercadoPago.status.in_(["PENDING", "IN_PROCESS", "ACTIVE"]),
    ).first()
    if not checkout:
        raise HTTPException(404, "Pagamento pendente não encontrado")
    token, _ = await obter_token_loja(db, loja_id)
    if checkout.payment_id:
        await cancelar_pagamento_por_id(access_token=token, payment_id=str(checkout.payment_id))
    checkout.status = "CANCELED"
    db.commit()
    return {"ok": True, "checkout_id": checkout_id, "status": "CANCELED"}


@router.put("/organizacao/{organizacao_id}")
async def salvar(
    organizacao_id: int,
    dados: TitularFinanceiroIn,
    loja_id: int | None = None,
    titularfinanceiro_id: int | None = None,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    if dados.organizacao_id != organizacao_id:
        raise HTTPException(status_code=422, detail="Organização divergente")
    if dados.tipotitular == "PF" and dados.dtnascimento is None:
        raise HTTPException(status_code=422, detail="Data de nascimento é obrigatória para PF")
    titular, loja = _resolver_titular(
        db,
        organizacao_id,
        payload,
        loja_id=loja_id,
        titularfinanceiro_id=titularfinanceiro_id,
        obrigatorio=False,
    )
    por_documento = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.cpfcnpj == dados.cpfcnpj
    ).first()
    if por_documento and por_documento.organizacao_id != organizacao_id:
        raise HTTPException(409, "Este CPF/CNPJ já pertence a outra organização no Clubbar")
    if titular and titular.asaas_account_id and titular.cpfcnpj != dados.cpfcnpj:
        raise HTTPException(409, "O CPF/CNPJ não pode ser alterado após a criação da subconta Asaas")
    if titular and titular.asaas_account_id and titular.tipotitular != dados.tipotitular:
        raise HTTPException(409, "O tipo de titular não pode ser alterado após a criação da subconta Asaas")
    if (
        titular
        and titular.asaas_account_id
        and titular.dtnascimento is not None
        and titular.dtnascimento != dados.dtnascimento
    ):
        raise HTTPException(409, "A data de nascimento não pode ser alterada após a criação da subconta Asaas")
    if por_documento and titular and por_documento.titularfinanceiro_id != titular.titularfinanceiro_id:
        raise HTTPException(409, "Este CPF/CNPJ já está cadastrado em outro titular")
    titular = titular or por_documento
    if titular is None:
        titular = TitularFinanceiro(organizacao_id=organizacao_id)
        db.add(titular)
    for campo, valor in dados.model_dump().items():
        if campo != "organizacao_id":
            setattr(titular, campo, valor)
    try:
        db.flush()
        if titular.asaas_account_id:
            await _sincronizar_dados_comerciais_asaas(titular, dados)
        if loja:
            if loja.titularfinanceiro_id and loja.titularfinanceiro_id != titular.titularfinanceiro_id:
                raise HTTPException(409, 'Altere o titular junto com o provedor na tela Recebimentos.')
            loja.titularfinanceiro_id = titular.titularfinanceiro_id
            sincronizar_integracao_asaas_da_loja(db, loja, titular)
        db.commit()
    except (IntegrityError, HTTPException) as exc:
        db.rollback()
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(409, "CPF/CNPJ ou conta Asaas já cadastrada") from exc
    db.refresh(titular)
    return _out(titular)


async def _asaas(method: str, path: str, api_key: str, json: dict | None = None, params: dict | None = None):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            f"{ASAAS_BASE_URL}{path}",
            headers={
                "accept": "application/json",
                "access_token": api_key,
                "User-Agent": "Clubbar/1.0",
            },
            json=json,
            params=params,
        )
    data = response.json() if response.content else {}
    if response.status_code >= 400:
        erros = data.get("errors")
        if isinstance(erros, list):
            descricoes = [
                str(item.get("description") or item.get("message") or "").strip()
                for item in erros
                if isinstance(item, dict)
            ]
            detalhe = " ".join(item for item in descricoes if item)
        else:
            detalhe = ""
        raise HTTPException(
            status_code=502,
            detail=detalhe or data.get("message") or "Erro na integração Asaas",
        )
    return data


async def _identificar_ambiente_credencial_asaas(api_key: str) -> str:
    """Identifica, sem alterar dados, em qual ambiente a chave é válida.

    A credencial de uma subconta só é aceita por um ambiente do Asaas. Consultar
    os dois endpoints evita tratar uma subconta real como se fosse de testes.
    """
    endpoints = (
        ("SANDBOX", "https://api-sandbox.asaas.com/v3/myAccount/status/"),
        ("PRODUCAO", "https://api.asaas.com/v3/myAccount/status/"),
    )
    respostas: list[int | None] = []
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for ambiente, url in endpoints:
                resposta = await client.get(
                    url,
                    headers={
                        "accept": "application/json",
                        "access_token": api_key,
                        "User-Agent": "Clubbar/1.0",
                    },
                )
                respostas.append(resposta.status_code)
                if resposta.is_success:
                    return ambiente
    except httpx.HTTPError:
        respostas.append(None)

    # Não confundir uma indisponibilidade do Asaas com uma chave inválida.
    if any(status is None or status >= 500 for status in respostas):
        return "INDISPONIVEL"
    return "INVALIDA"


async def _sincronizar_dados_comerciais_asaas(
    titular: TitularFinanceiro, dados: TitularFinanceiroIn
) -> None:
    """Sincroniza no Asaas os campos cadastrais editáveis da subconta."""
    if not titular.asaas_api_key_criptografada:
        return
    api_key = descriptografar_credencial(titular.asaas_api_key_criptografada)
    atuais = await _asaas("GET", "/myAccount/commercialInfo/", api_key)
    payload = {
        "personType": "JURIDICA" if dados.tipotitular == "PJ" else "FISICA",
        "cpfCnpj": titular.cpfcnpj,
        "birthDate": dados.dtnascimento.isoformat() if dados.dtnascimento else atuais.get("birthDate"),
        "incomeValue": float(dados.vrfaturamentomensal),
        "email": str(dados.email),
        "phone": dados.telefone,
        "mobilePhone": dados.telefone,
        "postalCode": dados.cep,
        "address": dados.endereco,
        "addressNumber": dados.numero,
        "complement": dados.complemento,
        "province": dados.bairro,
    }
    if dados.tipotitular == "PJ":
        payload["companyType"] = atuais.get("companyType") or "LIMITED"
        payload["companyName"] = dados.nmrazaosocial
        disponiveis = atuais.get("availableCompanyNames") or []
        if disponiveis and dados.nmrazaosocial not in disponiveis:
            raise HTTPException(
                status_code=422,
                detail="A razão social informada não está entre as denominações disponíveis no Asaas.",
            )
    await _asaas("POST", "/myAccount/commercialInfo/", api_key, payload)
    situacao = await _asaas("GET", "/myAccount/status/", api_key)
    geral = str(situacao.get("general") or "PENDING").upper()
    titular.status_asaas = {
        "APPROVED": "APROVADO",
        "REJECTED": "REJEITADO",
        "AWAITING_APPROVAL": "EM_ANALISE",
    }.get(geral, "PENDENTE_DOCUMENTOS")
    titular.dtultimaverificacao = datetime.now()


@router.delete("/organizacao/{organizacao_id}/titular/{titularfinanceiro_id}")
def excluir_titular(
    organizacao_id: int,
    titularfinanceiro_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    """Exclui um titular sem vínculos operacionais ainda ativos.

    Referências antigas de contratos e configurações de pagamento inativas são
    desvinculadas, preservando os registros históricos e permitindo que o
    titular seja removido da organização.
    """
    _validar_escopo(payload, organizacao_id)
    titular = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.titularfinanceiro_id == titularfinanceiro_id,
        TitularFinanceiro.organizacao_id == organizacao_id,
    ).first()
    if not titular:
        raise HTTPException(404, "Titular financeiro não encontrado nesta organização")

    motivos = _motivos_titular_em_uso(db, titular)
    if motivos:
        raise HTTPException(
            409,
            "Este titular não pode ser excluído porque já possui "
            f"{', '.join(motivos)}.",
        )
    try:
        # O contrato não depende do titular financeiro. Removemos somente a
        # referência operacional obsoleta; o contrato e seus dados históricos
        # permanecem intactos.
        db.query(LeadEstabelecimentoContrato).filter(
            LeadEstabelecimentoContrato.titularfinanceiro_id == titularfinanceiro_id,
        ).update(
            {LeadEstabelecimentoContrato.titularfinanceiro_id: None},
            synchronize_session=False,
        )

        # Mantém configurações MP inativas/pendentes para o histórico de
        # pagamentos, mas sem deixar uma FK apontando para o titular excluído.
        db.query(LojaMercadoPago).filter(
            LojaMercadoPago.titularfinanceiro_id == titularfinanceiro_id,
            LojaMercadoPago.statusintegracao != "ATIVA",
        ).update(
            {LojaMercadoPago.titularfinanceiro_id: None},
            synchronize_session=False,
        )
        db.delete(titular)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            "Este titular não pode ser excluído porque possui vínculos no Clubbar.",
        ) from exc
    return {"ok": True}


@router.patch("/organizacao/{organizacao_id}/titular/{titularfinanceiro_id}/inativar")
def inativar_titular(
    organizacao_id: int,
    titularfinanceiro_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    titular = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.titularfinanceiro_id == titularfinanceiro_id,
        TitularFinanceiro.organizacao_id == organizacao_id,
    ).first()
    if not titular:
        raise HTTPException(404, "Titular financeiro não encontrado nesta organização")
    if db.query(Loja).filter(Loja.organizacao_id == organizacao_id, Loja.titularfinanceiro_id == titularfinanceiro_id).first():
        raise HTTPException(409, 'Altere o titular das lojas vinculadas antes de inativá-lo.')
    if db.query(LojaMercadoPago).filter(LojaMercadoPago.titularfinanceiro_id == titularfinanceiro_id, LojaMercadoPago.statusintegracao == 'ATIVA').first():
        raise HTTPException(409, 'Desconecte a conta Mercado Pago antes de inativar o titular.')
    titular.sittitular = "INATIVO"
    db.commit()
    db.refresh(titular)
    return _out(titular)


@router.patch("/organizacao/{organizacao_id}/titular/{titularfinanceiro_id}/reativar")
def reativar_titular(
    organizacao_id: int,
    titularfinanceiro_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    titular = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.titularfinanceiro_id == titularfinanceiro_id,
        TitularFinanceiro.organizacao_id == organizacao_id,
    ).first()
    if not titular:
        raise HTTPException(404, "Titular financeiro não encontrado nesta organização")
    titular.sittitular = "ATIVO"
    db.commit()
    db.refresh(titular)
    return _out(titular)


@router.patch(
    "/organizacao/{organizacao_id}/titular/{titularfinanceiro_id}/dados-ativacao-asaas"
)
def atualizar_dados_ativacao_asaas(
    organizacao_id: int,
    titularfinanceiro_id: int,
    dados: DadosAtivacaoAsaasIn,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    """Registra os dados obrigatórios antes de criar a subconta Asaas."""
    _validar_escopo(payload, organizacao_id)
    titular = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.titularfinanceiro_id == titularfinanceiro_id,
        TitularFinanceiro.organizacao_id == organizacao_id,
    ).first()
    if not titular:
        raise HTTPException(404, "Titular financeiro não encontrado nesta organização")
    if titular.asaas_account_id:
        raise HTTPException(409, "A subconta Asaas deste titular já foi criada")
    if titular.tipotitular == "PF" and dados.dtnascimento is None:
        raise HTTPException(422, "Data de nascimento é obrigatória para pessoa física")

    titular.dtnascimento = dados.dtnascimento if titular.tipotitular == "PF" else None
    titular.vrfaturamentomensal = dados.vrfaturamentomensal
    db.commit()
    db.refresh(titular)
    return _out(titular)


@router.post(
    "/organizacao/{organizacao_id}/titular/{titularfinanceiro_id}/migrar-sandbox-producao"
)
async def migrar_vinculo_sandbox_para_producao(
    organizacao_id: int,
    titularfinanceiro_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    """Desvincula somente uma subconta comprovadamente criada no Sandbox.

    A subconta de teste continua existindo no Sandbox. O titular e seus dados
    permanecem no Clubbar para que a conta de produção seja criada com o mesmo
    CPF/CNPJ no fluxo normal de ativação.
    """
    _validar_escopo(payload, organizacao_id)
    if "api-sandbox.asaas.com" in ASAAS_BASE_URL.lower():
        raise HTTPException(
            status_code=409,
            detail="Esta migração deve ser executada somente no ambiente de produção.",
        )
    if not ASAAS_API_KEY:
        raise HTTPException(
            status_code=422,
            detail="A conta principal Asaas de produção não está configurada.",
        )

    titular = (
        db.query(TitularFinanceiro)
        .filter(
            TitularFinanceiro.titularfinanceiro_id == titularfinanceiro_id,
            TitularFinanceiro.organizacao_id == organizacao_id,
        )
        .first()
    )
    if not titular:
        raise HTTPException(404, "Titular financeiro não encontrado nesta organização")
    if not titular.asaas_account_id or not titular.asaas_api_key_criptografada:
        raise HTTPException(409, "Este titular não possui um vínculo Asaas para migrar.")

    api_key_antiga = descriptografar_credencial(titular.asaas_api_key_criptografada)
    ambiente_credencial = await _identificar_ambiente_credencial_asaas(api_key_antiga)
    if ambiente_credencial == "PRODUCAO":
        raise HTTPException(
            status_code=409,
            detail=(
                "A subconta vinculada já é de produção e não precisa ser migrada. "
                "Para proteger recebimentos reais, nenhuma alteração foi feita."
            ),
        )
    if ambiente_credencial == "INDISPONIVEL":
        raise HTTPException(
            status_code=503,
            detail=(
                "Não foi possível confirmar o ambiente da subconta porque o Asaas não respondeu "
                "normalmente. Tente novamente em alguns minutos; nenhuma alteração foi feita."
            ),
        )
    if ambiente_credencial != "SANDBOX":
        raise HTTPException(
            status_code=409,
            detail=(
                "A credencial armazenada não é válida nem no Sandbox nem na produção do Asaas. "
                "Ela pode ter sido revogada ou estar inconsistente; nenhuma alteração foi feita."
            ),
        )

    titular.asaas_account_id = None
    titular.asaas_wallet_id = None
    titular.asaas_api_key_criptografada = None
    titular.status_asaas = "NAO_INICIADO"
    titular.onboarding_url = None
    titular.dtultimaverificacao = datetime.now()

    lojas = (
        db.query(Loja)
        .filter(
            Loja.organizacao_id == organizacao_id,
            Loja.titularfinanceiro_id == titular.titularfinanceiro_id,
        )
        .all()
    )
    for loja in lojas:
        sincronizar_integracao_asaas_da_loja(db, loja, titular)
    db.commit()
    db.refresh(titular)
    return _out(titular)


async def _localizar_subconta_existente(documento: str, email: str) -> dict | None:
    """Localiza com segurança uma subconta da conta-pai antes de criar outra."""
    por_documento = await _asaas(
        "GET", "/accounts", ASAAS_API_KEY, params={"cpfCnpj": documento, "limit": 100}
    )
    encontradas = list(por_documento.get("data") or [])
    if not encontradas and email:
        por_email = await _asaas(
            "GET", "/accounts", ASAAS_API_KEY, params={"email": email, "limit": 100}
        )
        encontradas = [
            item for item in (por_email.get("data") or [])
            if normalizar_cpf_cnpj(str(item.get("cpfCnpj") or "")) == documento
        ]
    if len(encontradas) > 1:
        raise HTTPException(
            status_code=409,
            detail="Há mais de uma subconta Asaas para este CPF/CNPJ. Solicite a vinculação manual pelo Clubbar Admin.",
        )
    return encontradas[0] if encontradas else None


async def _nova_chave_subconta(account_id: str) -> str:
    try:
        resposta = await _asaas(
            "POST",
            f"/accounts/{account_id}/accessTokens",
            ASAAS_API_KEY,
            {"name": f"Clubbar {datetime.now():%Y-%m-%d %H:%M}"},
        )
    except HTTPException as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "A subconta já existe no Asaas, mas o Clubbar não conseguiu gerar uma nova chave para vinculá-la. "
                "Habilite temporariamente o gerenciamento de chaves de subcontas e autorize o IP da API no Asaas. "
                f"Detalhe do Asaas: {exc.detail}"
            ),
        ) from exc
    chave = resposta.get("access_token") or resposta.get("accessToken") or resposta.get("apiKey")
    if not chave:
        raise HTTPException(502, "O Asaas criou a credencial, mas não devolveu sua chave secreta.")
    return str(chave)


@router.get('/organizacao/{organizacao_id}/contas-extrato-mercado-pago')
def contas_extrato_mercado_pago(organizacao_id: int, loja_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_usuario_logado)):
    _validar_escopo(payload, organizacao_id)
    if str(payload.get('dscargo') or '').upper() not in {'SUPERADMIN', 'ADMIN'}:
        raise HTTPException(403, 'Somente administradores podem consultar pagamentos da conta Mercado Pago.')
    _, loja = _resolver_titular(db, organizacao_id, payload, loja_id=loja_id)
    historico = exists().where(CheckoutMercadoPago.loja_id == loja.loja_id, CheckoutMercadoPago.lojamercadopago_id == LojaMercadoPago.lojamercadopago_id)
    contas = db.query(LojaMercadoPago).filter(
        LojaMercadoPago.organizacao_id == organizacao_id, LojaMercadoPago.ambiente == APP_ENV,
        LojaMercadoPago.mercadopago_user_id.isnot(None),
        or_(historico, (LojaMercadoPago.titularfinanceiro_id == loja.titularfinanceiro_id) & (LojaMercadoPago.statusintegracao == 'ATIVA')),
    ).order_by(LojaMercadoPago.dtcriacao.desc()).all()
    return [{'id': c.lojamercadopago_id, 'nome': c.mercadopago_nome, 'conta': c.mercadopago_user_id, 'status': c.statusintegracao, 'disponivel': bool(c.access_token_criptografado)} for c in contas]


@router.get('/organizacao/{organizacao_id}/extrato-mercado-pago')
async def extrato_mercado_pago(
    organizacao_id: int, loja_id: int, data_inicio: date | None = None,
    data_fim: date | None = None, offset: int = 0,
    db: Session = Depends(get_db), payload: dict = Depends(get_usuario_logado),
    conta_id: int | None = None,
):
    _validar_escopo(payload, organizacao_id)
    if str(payload.get('dscargo') or '').upper() not in {'SUPERADMIN', 'ADMIN'}:
        raise HTTPException(403, 'Somente administradores podem consultar pagamentos da conta Mercado Pago.')
    _, loja = _resolver_titular(db, organizacao_id, payload, loja_id=loja_id)
    if conta_id is None:
        token, conta = await obter_token_loja(db, loja.loja_id)
    else:
        historico = db.query(CheckoutMercadoPago.checkout_mercadopago_id).filter_by(loja_id=loja.loja_id, lojamercadopago_id=conta_id).first()
        conta_atual = db.query(LojaMercadoPago).filter_by(lojamercadopago_id=conta_id, organizacao_id=organizacao_id, titularfinanceiro_id=loja.titularfinanceiro_id, ambiente=APP_ENV, statusintegracao='ATIVA').first()
        if not historico and not conta_atual:
            raise HTTPException(404, 'Conta não disponível para este estabelecimento.')
        if conta_atual and not historico:
            token, conta = await obter_token_loja(db, loja.loja_id)
        else:
            token, conta = await obter_token_loja(db, loja.loja_id, lojamercadopago_id=conta_id)
    hoje = date.today()
    inicio, fim = data_inicio or date(hoje.year, hoje.month, 1), data_fim or hoje
    if inicio > fim or offset < 0 or offset > 10000:
        raise HTTPException(422, 'Período ou paginação inválida.')
    try:
        pagamentos_loja = []
        cursor = 0
        async with httpx.AsyncClient(timeout=25) as cliente:
          while True:
            resposta = await cliente.get(
                f'{MERCADO_PAGO_API_BASE_URL}/v1/payments/search',
                headers={'Authorization': f'Bearer {token}'},
                params={'sort': 'date_created', 'criteria': 'desc', 'range': 'date_created',
                        'begin_date': f'{inicio.isoformat()}T00:00:00.000-03:00',
                        'end_date': f'{fim.isoformat()}T23:59:59.999-03:00',
                        'limit': 50, 'offset': cursor},
            )
            if resposta.is_error:
                raise HTTPException(502, 'Não foi possível consultar os pagamentos no Mercado Pago.')
            dados = resposta.json()
            itens = [item for item in dados.get('results', []) if isinstance(item, dict)]
            ids = [str(item.get('id')) for item in itens if item.get('id')]
            refs = [str(item.get('external_reference')) for item in itens if item.get('external_reference')]
            if ids or refs:
                from sqlalchemy import or_
                condicoes = []
                if ids:
                    condicoes.append(CheckoutMercadoPago.payment_id.in_(ids))
                if refs:
                    condicoes.append(CheckoutMercadoPago.external_reference.in_(refs))
                checkouts = db.query(CheckoutMercadoPago).filter(
                    CheckoutMercadoPago.loja_id == loja.loja_id, CheckoutMercadoPago.lojamercadopago_id == conta.lojamercadopago_id, or_(*condicoes),
                ).all()
                por_id = {str(c.payment_id): c for c in checkouts if c.payment_id}
                por_ref = {str(c.external_reference): c for c in checkouts if c.external_reference}
                for item in itens:
                    checkout = por_id.get(str(item.get('id') or '')) or por_ref.get(str(item.get('external_reference') or ''))
                    if checkout:
                        tipo = 'INGRESSO' if checkout.reserva_ingresso_id and not checkout.carrinho_id else 'PRODUTO' if checkout.carrinho_id and not checkout.reserva_ingresso_id else None
                        pagamentos_loja.append((item, tipo, checkout))
            cursor += len(itens)
            if not itens or cursor >= int((dados.get('paging') or {}).get('total') or 0):
                break
            if cursor >= 10000:
                raise HTTPException(422, 'O período possui muitos pagamentos. Selecione um período menor.')
    except (httpx.RequestError, ValueError) as exc:
        raise HTTPException(502, 'Não foi possível consultar os pagamentos no Mercado Pago.') from exc
    pagina = pagamentos_loja[offset:offset + 50]
    vendas = {c.venda_id for _, _, c in pagina if c.venda_id}
    reservas = {c.reserva_ingresso_id for _, _, c in pagina if c.reserva_ingresso_id}
    produtos_por_venda = {}
    if vendas:
        for venda_id, nome, quantidade in db.query(ItVenda.venda_id, Produto.nmproduto, ItVenda.qtitvenda).join(Produto, Produto.produto_id == ItVenda.produto_id).filter(ItVenda.venda_id.in_(vendas), ItVenda.tipoitem == 'PRODUTO').all():
            produtos_por_venda.setdefault(venda_id, []).append({'nome': nome, 'quantidade': quantidade})
    eventos_por_reserva = {}
    if reservas:
        for reserva_id, nome, quantidade in db.query(ReservaIngresso.reserva_ingresso_id, Evento.nmtituloevento, ReservaIngresso.qtreservada).join(Evento, Evento.evento_id == ReservaIngresso.evento_id).filter(ReservaIngresso.reserva_ingresso_id.in_(reservas)).all():
            eventos_por_reserva[reserva_id] = [{'nome': nome, 'quantidade': quantidade}]
    pagamentos = [{
        'id': str(item.get('id') or ''), 'data': item.get('date_created'),
        'descricao': item.get('description') or 'Pagamento',
        'tipo_venda': tipo,
        'itens': eventos_por_reserva.get(checkout.reserva_ingresso_id, []) if tipo == 'INGRESSO' else produtos_por_venda.get(checkout.venda_id, []),
        'nome_cliente': ' '.join(
            str(parte).strip()
            for parte in (
                (item.get('payer') or {}).get('first_name'),
                (item.get('payer') or {}).get('last_name'),
            )
            if str(parte or '').strip()
        ) or None,
        'status': item.get('status'),
        'valor': item.get('transaction_amount'), 'estornado': item.get('transaction_amount_refunded'),
        'metodo': item.get('payment_method_id'),
    } for item, tipo, checkout in pagina]
    total = len(pagamentos_loja)
    return {'pagamentos': pagamentos, 'total': total, 'possui_mais': offset + len(pagamentos) < total}


@router.get("/organizacao/{organizacao_id}/extrato-asaas")
async def extrato_asaas(
    organizacao_id: int,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    offset: int = 0,
    limite: int = 50,
    loja_id: int | None = None,
    titularfinanceiro_id: int | None = None,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    titular, loja = _resolver_titular(
        db,
        organizacao_id,
        payload,
        loja_id=loja_id,
        titularfinanceiro_id=titularfinanceiro_id,
    )
    if not titular.asaas_api_key_criptografada:
        raise HTTPException(422, "Ative os recebimentos no Asaas antes de consultar o extrato")
    api_key = descriptografar_credencial(titular.asaas_api_key_criptografada)
    hoje = date.today()
    inicio = data_inicio or date(hoje.year, hoje.month, 1)
    fim = data_fim or hoje
    if inicio > fim:
        raise HTTPException(422, "A data inicial não pode ser posterior à data final")
    limite = min(max(limite, 1), 100)
    saldo = await _asaas("GET", "/finance/balance", api_key)
    extrato = await _asaas("GET", "/financialTransactions", api_key, params={
        "startDate": inicio.isoformat(), "finishDate": fim.isoformat(),
        "offset": max(offset, 0), "limit": limite, "order": "desc",
    })
    cobrancas = await _asaas("GET", "/payments", api_key, params={
        "dateCreated[ge]": inicio.isoformat(), "dateCreated[le]": fim.isoformat(),
        "offset": 0, "limit": 100,
    })
    itens = []
    for item in extrato.get("data", []):
        itens.append({
            "id": item.get("id"),
            "data": item.get("date") or item.get("effectiveDate"),
            "tipo": item.get("type"),
            "descricao": item.get("description"),
            "valor": item.get("value"),
            "saldo": item.get("balance"),
            "pagamento_id": item.get("paymentId"),
            "transferencia_id": item.get("transferId"),
        })
    recebimentos_pendentes = []
    for item in cobrancas.get("data", []):
        if str(item.get("status") or "").upper() != "CONFIRMED":
            continue
        recebimentos_pendentes.append({
            "id": item.get("id"),
            "data": item.get("paymentDate") or item.get("confirmedDate") or item.get("dateCreated"),
            "tipo": item.get("billingType"), "status": item.get("status"),
            "descricao": item.get("description") or "Venda Clubbar",
            "valor_bruto": item.get("value"), "valor_liquido": item.get("netValue"),
            "data_prevista_credito": item.get("estimatedCreditDate") or item.get("creditDate"),
        })
    return {
        "titularfinanceiro_id": titular.titularfinanceiro_id,
        "loja_id": loja.loja_id if loja else None,
        "nmrazaosocial": titular.nmrazaosocial,
        "saldo": float(saldo.get("balance") or 0),
        "data_inicio": inicio,
        "data_fim": fim,
        "total": extrato.get("totalCount", len(itens)),
        "possui_mais": bool(extrato.get("hasMore")),
        "transacoes": itens,
        "total_pendente": float(sum(Decimal(str(item.get("valor_liquido") or 0)) for item in recebimentos_pendentes)),
        "recebimentos_pendentes": recebimentos_pendentes,
    }


def _loja_da_organizacao(db: Session, organizacao_id: int, loja_id: int) -> Loja:
    loja = db.query(Loja).filter(
        Loja.loja_id == loja_id,
        Loja.organizacao_id == organizacao_id,
    ).first()
    if not loja:
        raise HTTPException(404, "Estabelecimento não encontrado nesta organização")
    return loja


def _resolver_titular(
    db: Session,
    organizacao_id: int,
    payload: dict,
    *,
    loja_id: int | None = None,
    titularfinanceiro_id: int | None = None,
    obrigatorio: bool = True,
) -> tuple[TitularFinanceiro | None, Loja | None]:
    loja_escopo = payload.get("loja_id")
    if loja_escopo is not None:
        if loja_id is not None and int(loja_escopo) != loja_id:
            raise HTTPException(403, "Estabelecimento fora do seu acesso")
        loja_id = int(loja_escopo)

    loja = _loja_da_organizacao(db, organizacao_id, loja_id) if loja_id else None
    if loja and titularfinanceiro_id and loja.titularfinanceiro_id not in {
        None,
        titularfinanceiro_id,
    }:
        raise HTTPException(409, "O titular informado não está vinculado ao estabelecimento")

    id_titular = titularfinanceiro_id or (loja.titularfinanceiro_id if loja else None)
    if id_titular:
        titular = db.query(TitularFinanceiro).filter(
            TitularFinanceiro.titularfinanceiro_id == id_titular,
            TitularFinanceiro.organizacao_id == organizacao_id,
        ).first()
        if not titular:
            raise HTTPException(404, "Titular financeiro não encontrado nesta organização")
        return titular, loja

    if loja:
        if obrigatorio:
            raise HTTPException(422, "Cadastre e vincule o titular financeiro deste estabelecimento")
        return None, loja

    titulares = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.organizacao_id == organizacao_id
    ).order_by(TitularFinanceiro.titularfinanceiro_id).all()
    if not titulares:
        if obrigatorio:
            raise HTTPException(422, "Cadastre e vincule o titular financeiro deste estabelecimento")
        return None, loja
    if len(titulares) > 1:
        raise HTTPException(
            409,
            "Esta organização possui mais de um titular financeiro. Selecione o estabelecimento.",
        )
    return titulares[0], loja


@router.post("/organizacao/{organizacao_id}/ativar-recebimentos")
async def ativar_recebimentos(
    organizacao_id: int,
    loja_id: int | None = None,
    titularfinanceiro_id: int | None = None,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    titular, _ = _resolver_titular(
        db,
        organizacao_id,
        payload,
        loja_id=loja_id,
        titularfinanceiro_id=titularfinanceiro_id,
    )
    if titular.asaas_account_id:
        lojas = db.query(Loja).filter(
            Loja.organizacao_id == organizacao_id,
            Loja.titularfinanceiro_id == titular.titularfinanceiro_id,
        ).all()
        for loja in lojas:
            sincronizar_integracao_asaas_da_loja(db, loja, titular)
        db.commit()
        return _out(titular)
    if titular.tipotitular == "PF" and titular.dtnascimento is None:
        raise HTTPException(
            422,
            "Informe a data de nascimento do titular financeiro antes de ativar a subconta Asaas.",
        )
    if not titular.vrfaturamentomensal or titular.vrfaturamentomensal <= 0:
        raise HTTPException(
            422,
            "Informe a renda ou o faturamento mensal estimado antes de ativar a subconta Asaas.",
        )
    documento = titular.cpfcnpj
    conta = await _localizar_subconta_existente(documento, titular.email)
    conta_reutilizada = conta is not None
    if conta_reutilizada and conta.get("id"):
        vinculada = db.query(TitularFinanceiro).filter(
            TitularFinanceiro.asaas_account_id == str(conta["id"]),
            TitularFinanceiro.organizacao_id != organizacao_id,
        ).first()
        if vinculada:
            raise HTTPException(409, "Esta subconta Asaas já está vinculada a outra organização no Clubbar.")
    if conta is None:
        conta = await _asaas("POST", "/accounts", ASAAS_API_KEY, {
            "name": titular.nmrazaosocial,
            "email": titular.email,
            "cpfCnpj": documento,
            "birthDate": titular.dtnascimento.isoformat() if titular.dtnascimento else None,
            "companyType": "LIMITED" if titular.tipotitular == "PJ" else None,
            "mobilePhone": titular.telefone,
            "address": titular.endereco,
            "addressNumber": titular.numero,
            "complement": titular.complemento,
            "province": titular.bairro,
            "postalCode": titular.cep,
            "incomeValue": float(titular.vrfaturamentomensal),
        })
    account_id = conta.get("id")
    api_key = await _nova_chave_subconta(str(account_id)) if conta_reutilizada and account_id else conta.get("apiKey")
    wallet_id = conta.get("walletId")
    if not api_key or not wallet_id or not account_id:
        raise HTTPException(status_code=502, detail="Asaas não devolveu as credenciais da subconta")
    criptografada = criptografar_credencial(api_key)
    titular.asaas_account_id = account_id
    titular.asaas_wallet_id = wallet_id
    titular.asaas_api_key_criptografada = criptografada
    titular.status_asaas = "EM_ONBOARDING"
    titular.dtultimaverificacao = datetime.now()
    lojas = db.query(Loja).filter(
        Loja.organizacao_id == organizacao_id,
        Loja.titularfinanceiro_id == titular.titularfinanceiro_id,
    ).all()
    for loja in lojas:
        sincronizar_integracao_asaas_da_loja(db, loja, titular)
    db.commit()
    db.refresh(titular)
    return _out(titular)


@router.post("/organizacao/{organizacao_id}/verificar-asaas")
async def verificar_asaas(
    organizacao_id: int,
    loja_id: int | None = None,
    titularfinanceiro_id: int | None = None,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    titular, _ = _resolver_titular(
        db,
        organizacao_id,
        payload,
        loja_id=loja_id,
        titularfinanceiro_id=titularfinanceiro_id,
    )
    if not titular.asaas_api_key_criptografada:
        raise HTTPException(status_code=422, detail="Recebimentos ainda não foram ativados")
    api_key = descriptografar_credencial(titular.asaas_api_key_criptografada)
    situacao = await _asaas("GET", "/myAccount/status/", api_key)
    documentos = await _asaas("GET", "/myAccount/documents", api_key)
    geral = str(situacao.get("general") or "PENDING").upper()
    titular.status_asaas = {
        "APPROVED": "APROVADO",
        "REJECTED": "REJEITADO",
        "AWAITING_APPROVAL": "EM_ANALISE",
    }.get(geral, "PENDENTE_DOCUMENTOS")
    urls = [item.get("onboardingUrl") for item in documentos.get("data", []) if item.get("onboardingUrl")]
    titular.onboarding_url = urls[0] if urls else titular.onboarding_url
    titular.dtultimaverificacao = datetime.now()
    lojas_titular = db.query(Loja).filter(
        Loja.organizacao_id == organizacao_id,
        Loja.titularfinanceiro_id == titular.titularfinanceiro_id,
    ).all()
    loja_ids_titular = [loja.loja_id for loja in lojas_titular]
    for loja in lojas_titular:
        sincronizar_integracao_asaas_da_loja(db, loja, titular)
    publicacoes = {"agendas_publicadas": 0, "cardapios_publicados": 0}
    if titular.status_asaas == "APROVADO":
        publicacoes = publicar_conteudos_aguardando_asaas(
            db, organizacao_id, loja_ids=loja_ids_titular
        )
    db.commit()
    db.refresh(titular)
    retorno = _out(titular)
    retorno["situacao"] = situacao
    retorno["documentos"] = documentos.get("data", [])
    retorno["publicacoes_automaticas"] = publicacoes
    return retorno


@router.post("/organizacao/{organizacao_id}/aprovar-sandbox")
async def aprovar_subconta_sandbox(
    organizacao_id: int,
    loja_id: int | None = None,
    titularfinanceiro_id: int | None = None,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    if APP_ENV in {"production", "prod"} or ambiente_asaas() != "sandbox":
        raise HTTPException(status_code=403, detail="A aprovação simulada existe somente no Sandbox")
    titular, _ = _resolver_titular(
        db,
        organizacao_id,
        payload,
        loja_id=loja_id,
        titularfinanceiro_id=titularfinanceiro_id,
    )
    if not titular.asaas_api_key_criptografada:
        raise HTTPException(status_code=422, detail="Crie a subconta antes de aprová-la")
    api_key = descriptografar_credencial(titular.asaas_api_key_criptografada)
    await _asaas("POST", "/sandbox/myAccount/approve", api_key)
    return await verificar_asaas(
        organizacao_id,
        loja_id,
        titularfinanceiro_id,
        db,
        payload,
    )
