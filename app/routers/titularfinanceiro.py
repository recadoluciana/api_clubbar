from datetime import date, datetime
from decimal import Decimal
import os
import secrets

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from app.core.config import APP_ENV, ASAAS_API_KEY
from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial, hash_token_webhook
from app.core.permissoes_loja import validar_gerenciamento_organizacao
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.loja import Loja
from app.models.lojaasaas import LojaAsaas
from app.models.titularfinanceiro import TitularFinanceiro


router = APIRouter(prefix="/titular-financeiro", tags=["Titular financeiro"])
ASAAS_BASE_URL = os.getenv("ASAAS_BASE_URL", "https://api-sandbox.asaas.com/v3").rstrip("/")


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

    @field_validator("cpfcnpj", "cep", "telefone")
    @classmethod
    def somente_numeros(cls, valor: str) -> str:
        return "".join(c for c in valor if c.isdigit())


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
            "status_asaas", "onboarding_url", "dtultimaverificacao",
        )
    }


@router.get("/organizacao/{organizacao_id}")
def consultar(organizacao_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_usuario_logado)):
    _validar_escopo(payload, organizacao_id)
    titular = db.query(TitularFinanceiro).filter(TitularFinanceiro.organizacao_id == organizacao_id).first()
    return _out(titular) if titular else None


@router.get("/organizacao/{organizacao_id}/todos")
def listar_titulares(
    organizacao_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    return [
        _out(item)
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
    titular = TitularFinanceiro(**dados.model_dump())
    db.add(titular)
    db.commit()
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
    loja.titularfinanceiro_id = titularfinanceiro_id
    db.commit()
    return {"ok": True, "loja_id": loja_id, "titularfinanceiro_id": titularfinanceiro_id}


@router.put("/organizacao/{organizacao_id}")
def salvar(organizacao_id: int, dados: TitularFinanceiroIn, db: Session = Depends(get_db), payload: dict = Depends(get_usuario_logado)):
    _validar_escopo(payload, organizacao_id)
    if dados.organizacao_id != organizacao_id:
        raise HTTPException(status_code=422, detail="Organização divergente")
    if dados.tipotitular == "PF" and dados.dtnascimento is None:
        raise HTTPException(status_code=422, detail="Data de nascimento é obrigatória para PF")
    titular = db.query(TitularFinanceiro).filter(TitularFinanceiro.organizacao_id == organizacao_id).first()
    if titular is None:
        titular = TitularFinanceiro(organizacao_id=organizacao_id)
        db.add(titular)
    for campo, valor in dados.model_dump().items():
        if campo != "organizacao_id":
            setattr(titular, campo, valor)
    db.commit()
    db.refresh(titular)
    return _out(titular)


async def _asaas(method: str, path: str, api_key: str, json: dict | None = None):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            f"{ASAAS_BASE_URL}{path}",
            headers={"accept": "application/json", "access_token": api_key},
            json=json,
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


@router.post("/organizacao/{organizacao_id}/ativar-recebimentos")
async def ativar_recebimentos(organizacao_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_usuario_logado)):
    _validar_escopo(payload, organizacao_id)
    titular = db.query(TitularFinanceiro).filter(TitularFinanceiro.organizacao_id == organizacao_id).first()
    if not titular:
        raise HTTPException(status_code=422, detail="Preencha os dados financeiros antes de ativar recebimentos")
    if titular.asaas_account_id:
        return _out(titular)
    documento = titular.cpfcnpj
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
    api_key = conta.get("apiKey")
    wallet_id = conta.get("walletId")
    account_id = conta.get("id")
    if not api_key or not wallet_id or not account_id:
        raise HTTPException(status_code=502, detail="Asaas não devolveu as credenciais da subconta")
    criptografada = criptografar_credencial(api_key)
    titular.asaas_account_id = account_id
    titular.asaas_wallet_id = wallet_id
    titular.asaas_api_key_criptografada = criptografada
    titular.status_asaas = "EM_ONBOARDING"
    titular.dtultimaverificacao = datetime.now()
    ambiente = "production" if APP_ENV in {"production", "prod"} else "sandbox"
    lojas = db.query(Loja).filter(
        Loja.organizacao_id == organizacao_id,
        (Loja.titularfinanceiro_id.is_(None))
        | (Loja.titularfinanceiro_id == titular.titularfinanceiro_id),
    ).all()
    for loja in lojas:
        loja.titularfinanceiro_id = titular.titularfinanceiro_id
        config = db.query(LojaAsaas).filter(LojaAsaas.loja_id == loja.loja_id, LojaAsaas.ambiente == ambiente).first()
        if config is None:
            token = secrets.token_urlsafe(32)
            config = LojaAsaas(
                organizacao_id=organizacao_id, loja_id=loja.loja_id, ambiente=ambiente,
                webhook_token_hash=hash_token_webhook(token),
            )
            db.add(config)
        config.asaas_account_id = account_id
        config.asaas_wallet_id = wallet_id
        config.asaas_api_key_criptografada = criptografada
        config.statusintegracao = "PENDENTE"
    db.commit()
    db.refresh(titular)
    return _out(titular)


@router.post("/organizacao/{organizacao_id}/verificar-asaas")
async def verificar_asaas(organizacao_id: int, db: Session = Depends(get_db), payload: dict = Depends(get_usuario_logado)):
    _validar_escopo(payload, organizacao_id)
    titular = db.query(TitularFinanceiro).filter(TitularFinanceiro.organizacao_id == organizacao_id).first()
    if not titular or not titular.asaas_api_key_criptografada:
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
    ambiente = "production" if APP_ENV in {"production", "prod"} else "sandbox"
    lojas_titular = db.query(Loja.loja_id).filter(
        Loja.organizacao_id == organizacao_id,
        Loja.titularfinanceiro_id == titular.titularfinanceiro_id,
    )
    for config in db.query(LojaAsaas).filter(
        LojaAsaas.organizacao_id == organizacao_id,
        LojaAsaas.loja_id.in_(lojas_titular),
        LojaAsaas.ambiente == ambiente,
    ).all():
        config.statusintegracao = "ATIVA" if titular.status_asaas == "APROVADO" else "PENDENTE"
    db.commit()
    db.refresh(titular)
    retorno = _out(titular)
    retorno["situacao"] = situacao
    retorno["documentos"] = documentos.get("data", [])
    return retorno


@router.post("/organizacao/{organizacao_id}/aprovar-sandbox")
async def aprovar_subconta_sandbox(
    organizacao_id: int,
    db: Session = Depends(get_db),
    payload: dict = Depends(get_usuario_logado),
):
    _validar_escopo(payload, organizacao_id)
    if APP_ENV in {"production", "prod"}:
        raise HTTPException(status_code=403, detail="A aprovação simulada existe somente no Sandbox")
    titular = db.query(TitularFinanceiro).filter(
        TitularFinanceiro.organizacao_id == organizacao_id
    ).first()
    if not titular or not titular.asaas_api_key_criptografada:
        raise HTTPException(status_code=422, detail="Crie a subconta antes de aprová-la")
    api_key = descriptografar_credencial(titular.asaas_api_key_criptografada)
    await _asaas("POST", "/sandbox/myAccount/approve", api_key)
    return await verificar_asaas(organizacao_id, db, payload)
