from datetime import date, datetime
from decimal import Decimal
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import APP_ENV, ASAAS_API_KEY
from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial
from app.core.permissoes_loja import validar_gerenciamento_organizacao
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.loja import Loja
from app.services.publicacao_pendente_service import publicar_conteudos_aguardando_asaas
from app.services.titular_financeiro_service import sincronizar_integracao_asaas_da_loja
from app.models.titularfinanceiro import TitularFinanceiro
from app.utils.documento import normalizar_cpf_cnpj


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
    retorno = _out(titular)
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
    loja.titularfinanceiro_id = titularfinanceiro_id
    sincronizar_integracao_asaas_da_loja(db, loja, titular)
    db.commit()
    return {"ok": True, "loja_id": loja_id, "titularfinanceiro_id": titularfinanceiro_id}


@router.put("/organizacao/{organizacao_id}")
def salvar(
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
    if por_documento and titular and por_documento.titularfinanceiro_id != titular.titularfinanceiro_id:
        raise HTTPException(409, "Este CPF/CNPJ já está cadastrado em outro titular")
    titular = titular or por_documento
    if titular is None:
        titular = TitularFinanceiro(organizacao_id=organizacao_id)
        db.add(titular)
    for campo, valor in dados.model_dump().items():
        if campo != "organizacao_id":
            setattr(titular, campo, valor)
    db.flush()
    if loja:
        loja.titularfinanceiro_id = titular.titularfinanceiro_id
        sincronizar_integracao_asaas_da_loja(db, loja, titular)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "CPF/CNPJ ou conta Asaas já cadastrada") from exc
    db.refresh(titular)
    return _out(titular)


async def _asaas(method: str, path: str, api_key: str, json: dict | None = None, params: dict | None = None):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(
            method,
            f"{ASAAS_BASE_URL}{path}",
            headers={"accept": "application/json", "access_token": api_key},
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
    if APP_ENV in {"production", "prod"}:
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
