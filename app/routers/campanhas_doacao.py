from __future__ import annotations

import os
import shutil
import uuid
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.core.config import ASAAS_API_KEY, UPLOAD_CAMPANHAS
from app.core.credential_crypto import criptografar_credencial, descriptografar_credencial
from app.models.campanha_doacao import CampanhaDoacao
from app.models.evento import Evento
from app.models.loja import Loja
from app.models.reserva_ingresso import ReservaIngresso
from app.services.campanha_doacao_service import (
    carteira_asaas_valida,
    conta_beneficiaria_aprovada,
    dados_publicos_campanha,
    obter_campanha_doacao_vigente,
    obter_campanha_para_reserva,
)
from app.utils.documento import normalizar_cpf_cnpj


router = APIRouter(prefix="/campanhas-doacao", tags=["Campanhas de doação"])
ASAAS_BASE_URL = os.getenv("ASAAS_BASE_URL", "https://api-sandbox.asaas.com/v3").rstrip("/")


class BeneficiarioAsaasIn(BaseModel):
    """Dados reais da entidade necessários para criar sua subconta Asaas."""

    cpf_cnpj: str = Field(min_length=11, max_length=18)
    email: EmailStr
    celular: str = Field(min_length=10, max_length=25)
    data_nascimento: date | None = None
    faturamento_mensal: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    endereco: str = Field(min_length=2, max_length=255)
    numero: str = Field(min_length=1, max_length=20)
    complemento: str | None = Field(default=None, max_length=120)
    bairro: str = Field(min_length=2, max_length=120)
    cep: str = Field(min_length=8, max_length=9)

    @field_validator("cpf_cnpj")
    @classmethod
    def validar_documento(cls, valor: str) -> str:
        try:
            return normalizar_cpf_cnpj(valor) or ""
        except ValueError as erro:
            raise ValueError(str(erro)) from erro

    @field_validator("celular", "cep")
    @classmethod
    def apenas_numeros(cls, valor: str) -> str:
        return "".join(caractere for caractere in valor if caractere.isdigit())

    @model_validator(mode="after")
    def exigir_nascimento_para_pf(self):
        if len(self.cpf_cnpj) == 11 and self.data_nascimento is None:
            raise ValueError("Informe a data de nascimento para beneficiário pessoa física.")
        return self


class CampanhaDoacaoIn(BaseModel):
    nmcampanha: str = Field(min_length=3, max_length=120)
    nmbeficiario: str = Field(min_length=3, max_length=160)
    dsmensagem: str | None = Field(default=None, max_length=1000)
    chavepix: str = Field(min_length=3, max_length=160)
    # O Partner envia esta informação apenas ao editar campanhas antigas. Para
    # novos cadastros, a API cria a subconta e recebe o walletId do Asaas.
    asaas_wallet_id: str | None = Field(default=None, max_length=100)
    beneficiario_asaas: BeneficiarioAsaasIn | None = None
    percentual_doacao: Decimal = Field(gt=0, le=100, max_digits=7, decimal_places=4)
    evento_id: int | None = None
    sitcampanha: str = Field(default="ATIVA", pattern="^(ATIVA|INATIVA)$")
    dtinicio: datetime | None = None
    dtfim: datetime | None = None

    @field_validator("nmcampanha", "nmbeficiario", "chavepix")
    @classmethod
    def remover_espacos(cls, valor: str) -> str:
        valor = " ".join(valor.split())
        if not valor:
            raise ValueError("Informe este campo.")
        return valor

    @field_validator("asaas_wallet_id")
    @classmethod
    def validar_wallet_asaas(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        if not valor:
            return None
        try:
            return str(UUID(valor))
        except ValueError as erro:
            raise ValueError(
                "Informe o Wallet ID do Asaas; a chave PIX não serve para split."
            ) from erro

    @field_validator("dsmensagem")
    @classmethod
    def normalizar_mensagem(cls, valor: str | None) -> str | None:
        valor = " ".join((valor or "").split())
        return valor or None

    @model_validator(mode="after")
    def validar_periodo(self):
        if not self.asaas_wallet_id and not self.beneficiario_asaas:
            raise ValueError("Cadastre os dados da subconta Asaas do beneficiário.")
        if self.dtinicio and self.dtfim and self.dtfim < self.dtinicio:
            raise ValueError("A data final não pode ser anterior à data inicial.")
        return self


def _saida(campanha: CampanhaDoacao) -> dict:
    return {
        "campanha_doacao_id": int(campanha.campanhadoacao_id),
        "organizacao_id": int(campanha.organizacao_id),
        "loja_id": int(campanha.loja_id),
        "evento_id": int(campanha.evento_id) if campanha.evento_id else None,
        "nome": campanha.nmcampanha,
        "beneficiario": campanha.nmbeficiario,
        "url_logo": campanha.urllogocampanha,
        "mensagem": campanha.dsmensagem,
        "chave_pix": campanha.chavepix,
        "asaas_wallet_id": campanha.asaas_wallet_id,
        "asaas_account_id": campanha.asaas_account_id,
        "status_asaas": campanha.status_asaas or "PENDENTE",
        "onboarding_url": campanha.onboarding_url,
        "pode_ativar": conta_beneficiaria_aprovada(campanha),
        "percentual_doacao": float(campanha.percentual_doacao),
        "situacao": campanha.sitcampanha,
        "data_inicio": campanha.dtinicio,
        "data_fim": campanha.dtfim,
        "data_criacao": campanha.dtcriacao,
    }


def _salvar_logo(arquivo: UploadFile) -> str:
    extensao = os.path.splitext(arquivo.filename or "")[1].lower()
    if extensao not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise HTTPException(422, "Use uma imagem JPG, PNG ou WebP.")
    nome = f"campanha_{uuid.uuid4().hex}{extensao}"
    with open(UPLOAD_CAMPANHAS / nome, "wb") as destino:
        shutil.copyfileobj(arquivo.file, destino)
    return f"/uploads/campanhas/{nome}"


def _loja_gerenciavel(db: Session, loja_id: int, usuario: dict) -> Loja:
    loja = db.query(Loja).filter(Loja.loja_id == loja_id).first()
    if not loja:
        raise HTTPException(404, "Estabelecimento não encontrado.")
    validar_mutacao_loja(usuario, loja.organizacao_id, loja.loja_id)
    return loja


def _validar_evento(db: Session, loja: Loja, evento_id: int | None) -> None:
    if evento_id is None:
        return
    evento = (
        db.query(Evento)
        .filter(Evento.evento_id == evento_id, Evento.loja_id == loja.loja_id)
        .first()
    )
    if not evento:
        raise HTTPException(422, "O evento não pertence a este estabelecimento.")


def _desativar_campanhas_mesmo_escopo(
    db: Session, *, loja_id: int, evento_id: int | None, exceto_id: int | None = None
) -> None:
    consulta = db.query(CampanhaDoacao).filter(
        CampanhaDoacao.loja_id == loja_id,
        CampanhaDoacao.sitcampanha == "ATIVA",
        CampanhaDoacao.evento_id.is_(None)
        if evento_id is None
        else CampanhaDoacao.evento_id == evento_id,
    )
    if exceto_id:
        consulta = consulta.filter(CampanhaDoacao.campanhadoacao_id != exceto_id)
    consulta.update({CampanhaDoacao.sitcampanha: "INATIVA"}, synchronize_session=False)


async def _asaas(
    method: str,
    path: str,
    api_key: str,
    json: dict | None = None,
    params: dict | None = None,
) -> dict:
    if not api_key:
        raise HTTPException(503, "A conta global Asaas do Clubbar não está configurada.")
    async with httpx.AsyncClient(timeout=30) as client:
        resposta = await client.request(
            method,
            f"{ASAAS_BASE_URL}{path}",
            headers={"accept": "application/json", "access_token": api_key},
            json=json,
            params=params,
        )
    dados = resposta.json() if resposta.content else {}
    if resposta.status_code >= 400:
        erros = dados.get("errors") if isinstance(dados, dict) else None
        detalhes = " ".join(
            str(item.get("description") or item.get("message") or "").strip()
            for item in (erros or [])
            if isinstance(item, dict)
        )
        raise HTTPException(502, detalhes or dados.get("message") or "Erro na integração Asaas")
    return dados


def _situacao_asaas(status_asaas: dict) -> str:
    geral = str(status_asaas.get("general") or "PENDING").upper()
    return {
        "APPROVED": "APROVADO",
        "REJECTED": "REJEITADO",
        "AWAITING_APPROVAL": "EM_ANALISE",
    }.get(geral, "PENDENTE_DOCUMENTOS")


async def _criar_subconta_beneficiaria(
    nome: str, dados: BeneficiarioAsaasIn
) -> tuple[str, str, str, str | None]:
    existentes = await _asaas(
        "GET", "/accounts", ASAAS_API_KEY,
        params={"cpfCnpj": dados.cpf_cnpj, "limit": 2},
    )
    if existentes.get("data"):
        raise HTTPException(
            409,
            "Já existe uma subconta Asaas para este CPF/CNPJ. Não crie uma duplicada.",
        )
    conta = await _asaas("POST", "/accounts", ASAAS_API_KEY, {
        "name": nome,
        "email": str(dados.email),
        "cpfCnpj": dados.cpf_cnpj,
        "birthDate": dados.data_nascimento.isoformat() if dados.data_nascimento else None,
        "companyType": "ASSOCIATION" if len(dados.cpf_cnpj) == 14 else None,
        "mobilePhone": dados.celular,
        "address": dados.endereco,
        "addressNumber": dados.numero,
        "complement": dados.complemento,
        "province": dados.bairro,
        "postalCode": dados.cep,
        "incomeValue": float(dados.faturamento_mensal),
    })
    account_id = str(conta.get("id") or "")
    wallet_id = str(conta.get("walletId") or "")
    api_key = str(conta.get("apiKey") or "")
    if not account_id or not wallet_id or not api_key:
        raise HTTPException(502, "Asaas não devolveu as credenciais da subconta beneficiária.")
    situacao = await _asaas("GET", "/myAccount/status/", api_key)
    return account_id, wallet_id, api_key, _situacao_asaas(situacao)


async def _atualizar_status_beneficiario(campanha: CampanhaDoacao) -> str:
    if not campanha.asaas_api_key_criptografada:
        raise HTTPException(
            422,
            "Esta campanha não possui uma subconta beneficiária gerenciada pelo Clubbar.",
        )
    api_key = descriptografar_credencial(campanha.asaas_api_key_criptografada)
    situacao = await _asaas("GET", "/myAccount/status/", api_key)
    campanha.status_asaas = _situacao_asaas(situacao)
    return campanha.status_asaas


@router.get("/vigente")
def consultar_vigente(
    loja_id: int,
    reserva_ingresso_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Consulta pública, usada somente para transparência no checkout."""
    if reserva_ingresso_id:
        reserva = (
            db.query(ReservaIngresso)
            .filter(
                ReservaIngresso.reserva_ingresso_id == reserva_ingresso_id,
                ReservaIngresso.loja_id == loja_id,
            )
            .first()
        )
        if not reserva:
            raise HTTPException(404, "Reserva não encontrada.")
        campanha = obter_campanha_para_reserva(db, reserva)
    else:
        campanha = obter_campanha_doacao_vigente(db, loja_id=loja_id)
    return {"campanha": dados_publicos_campanha(campanha)}


@router.get("/participantes")
def listar_participantes(db: Session = Depends(get_db)):
    """Lista uma campanha vigente por estabelecimento para a Home pública."""
    agora = datetime.now()
    campanhas = (
        db.query(CampanhaDoacao, Loja)
        .join(Loja, Loja.loja_id == CampanhaDoacao.loja_id)
        .filter(
            CampanhaDoacao.sitcampanha == "ATIVA",
            or_(CampanhaDoacao.dtinicio.is_(None), CampanhaDoacao.dtinicio <= agora),
            or_(CampanhaDoacao.dtfim.is_(None), CampanhaDoacao.dtfim >= agora),
        )
        .order_by(CampanhaDoacao.dtcriacao.desc())
        .all()
    )
    participantes = []
    lojas_incluidas: set[int] = set()
    for campanha, loja in campanhas:
        loja_id = int(loja.loja_id)
        if loja_id in lojas_incluidas or not conta_beneficiaria_aprovada(campanha):
            continue
        lojas_incluidas.add(loja_id)
        participantes.append({
            "loja_id": loja_id,
            "loja_nome": loja.nmloja,
            "loja_logo_url": loja.urllogoloja,
            "campanha_doacao_id": int(campanha.campanhadoacao_id),
            "campanha_nome": campanha.nmcampanha,
            "campanha_logo_url": campanha.urllogocampanha,
            "beneficiario": campanha.nmbeficiario,
            "percentual_doacao": float(campanha.percentual_doacao),
        })
    return {"participantes": participantes}


@router.get("/lojas/{loja_id}")
def listar_por_loja(
    loja_id: int,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    _loja_gerenciavel(db, loja_id, usuario)
    itens = (
        db.query(CampanhaDoacao)
        .filter(CampanhaDoacao.loja_id == loja_id)
        .order_by(CampanhaDoacao.evento_id.is_(None).desc(), CampanhaDoacao.dtcriacao.desc())
        .all()
    )
    return [_saida(item) for item in itens]


@router.post("/lojas/{loja_id}", status_code=status.HTTP_201_CREATED)
async def criar(
    loja_id: int,
    dados: CampanhaDoacaoIn,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja = _loja_gerenciavel(db, loja_id, usuario)
    _validar_evento(db, loja, dados.evento_id)
    valores = dados.model_dump(exclude={"beneficiario_asaas"})
    if dados.beneficiario_asaas:
        conta_id, wallet_id, api_key, status_asaas = await _criar_subconta_beneficiaria(
            dados.nmbeficiario, dados.beneficiario_asaas
        )
        valores.update({
            "asaas_wallet_id": wallet_id,
            "asaas_account_id": conta_id,
            "asaas_api_key_criptografada": criptografar_credencial(api_key),
            "status_asaas": status_asaas,
        })
    else:
        # Uma carteira inserida manualmente não comprova que a conta está apta
        # a receber. Campanhas legadas podem continuar inativas para ajuste.
        valores["status_asaas"] = "PENDENTE_DOCUMENTOS"
    if valores["sitcampanha"] == "ATIVA" and valores.get("status_asaas") != "APROVADO":
        valores["sitcampanha"] = "INATIVA"
    if valores["sitcampanha"] == "ATIVA":
        _desativar_campanhas_mesmo_escopo(
            db, loja_id=loja_id, evento_id=dados.evento_id
        )
    campanha = CampanhaDoacao(
        organizacao_id=loja.organizacao_id,
        loja_id=loja_id,
        **valores,
    )
    db.add(campanha)
    db.commit()
    db.refresh(campanha)
    return _saida(campanha)


@router.put("/{campanha_id}")
async def alterar(
    campanha_id: int,
    dados: CampanhaDoacaoIn,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    campanha = (
        db.query(CampanhaDoacao)
        .filter(CampanhaDoacao.campanhadoacao_id == campanha_id)
        .first()
    )
    if not campanha:
        raise HTTPException(404, "Campanha não encontrada.")
    loja = _loja_gerenciavel(db, int(campanha.loja_id), usuario)
    _validar_evento(db, loja, dados.evento_id)
    if dados.beneficiario_asaas:
        raise HTTPException(
            422,
            "Crie uma nova campanha para cadastrar outra subconta beneficiária.",
        )
    if dados.asaas_wallet_id != campanha.asaas_wallet_id:
        raise HTTPException(422, "O Wallet ID da subconta beneficiária não pode ser alterado manualmente.")
    if dados.sitcampanha == "ATIVA":
        await _atualizar_status_beneficiario(campanha)
        if campanha.status_asaas != "APROVADO":
            db.commit()
            raise HTTPException(
                422,
                "A subconta do beneficiário ainda não está aprovada no Asaas. A campanha permanece inativa.",
            )
        _desativar_campanhas_mesmo_escopo(
            db,
            loja_id=int(loja.loja_id),
            evento_id=dados.evento_id,
            exceto_id=campanha_id,
        )
    for campo, valor in dados.model_dump(exclude={"beneficiario_asaas"}).items():
        setattr(campanha, campo, valor)
    db.commit()
    db.refresh(campanha)
    return _saida(campanha)


@router.post("/{campanha_id}/ativar")
async def ativar(
    campanha_id: int,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    """Confere a subconta no Asaas e só então publica a campanha no Client."""
    campanha = (
        db.query(CampanhaDoacao)
        .filter(CampanhaDoacao.campanhadoacao_id == campanha_id)
        .first()
    )
    if not campanha:
        raise HTTPException(404, "Campanha não encontrada.")
    _loja_gerenciavel(db, int(campanha.loja_id), usuario)
    situacao = await _atualizar_status_beneficiario(campanha)
    if situacao != "APROVADO":
        campanha.sitcampanha = "INATIVA"
        db.commit()
        raise HTTPException(
            422,
            "A subconta do beneficiário ainda não está aprovada no Asaas. Complete o cadastro e tente novamente.",
        )
    _desativar_campanhas_mesmo_escopo(
        db,
        loja_id=int(campanha.loja_id),
        evento_id=int(campanha.evento_id) if campanha.evento_id else None,
        exceto_id=campanha_id,
    )
    campanha.sitcampanha = "ATIVA"
    db.commit()
    db.refresh(campanha)
    return _saida(campanha)


@router.post("/{campanha_id}/logo")
def enviar_logo(
    campanha_id: int,
    logo: UploadFile = File(...),
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    campanha = (
        db.query(CampanhaDoacao)
        .filter(CampanhaDoacao.campanhadoacao_id == campanha_id)
        .first()
    )
    if not campanha:
        raise HTTPException(404, "Campanha não encontrada.")
    _loja_gerenciavel(db, int(campanha.loja_id), usuario)
    campanha.urllogocampanha = _salvar_logo(logo)
    db.commit()
    db.refresh(campanha)
    return _saida(campanha)


@router.delete("/{campanha_id}")
def inativar(
    campanha_id: int,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    campanha = (
        db.query(CampanhaDoacao)
        .filter(CampanhaDoacao.campanhadoacao_id == campanha_id)
        .first()
    )
    if not campanha:
        raise HTTPException(404, "Campanha não encontrada.")
    _loja_gerenciavel(db, int(campanha.loja_id), usuario)
    campanha.sitcampanha = "INATIVA"
    db.commit()
    return {"ok": True}
