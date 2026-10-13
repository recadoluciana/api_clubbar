from __future__ import annotations

import os
import shutil
import uuid
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.core.config import UPLOAD_CAMPANHAS
from app.models.campanha_doacao import CampanhaDoacao
from app.models.evento import Evento
from app.models.loja import Loja
from app.models.reserva_ingresso import ReservaIngresso
from app.services.campanha_doacao_service import (
    carteira_asaas_valida,
    dados_publicos_campanha,
    obter_campanha_doacao_vigente,
    obter_campanha_para_reserva,
)


router = APIRouter(prefix="/campanhas-doacao", tags=["Campanhas de doação"])


class CampanhaDoacaoIn(BaseModel):
    nmcampanha: str = Field(min_length=3, max_length=120)
    nmbeficiario: str = Field(min_length=3, max_length=160)
    dsmensagem: str | None = Field(default=None, max_length=1000)
    chavepix: str = Field(min_length=3, max_length=160)
    asaas_wallet_id: str = Field(min_length=8, max_length=100)
    percentual_doacao: Decimal = Field(gt=0, le=100, max_digits=7, decimal_places=4)
    evento_id: int | None = None
    sitcampanha: str = Field(default="ATIVA", pattern="^(ATIVA|INATIVA)$")
    dtinicio: datetime | None = None
    dtfim: datetime | None = None

    @field_validator("nmcampanha", "nmbeficiario", "chavepix", "asaas_wallet_id")
    @classmethod
    def remover_espacos(cls, valor: str) -> str:
        valor = " ".join(valor.split())
        if not valor:
            raise ValueError("Informe este campo.")
        return valor

    @field_validator("asaas_wallet_id")
    @classmethod
    def validar_wallet_asaas(cls, valor: str) -> str:
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
        if loja_id in lojas_incluidas or not carteira_asaas_valida(campanha.asaas_wallet_id):
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
def criar(
    loja_id: int,
    dados: CampanhaDoacaoIn,
    usuario: dict = Depends(get_usuario_logado),
    db: Session = Depends(get_db),
):
    loja = _loja_gerenciavel(db, loja_id, usuario)
    _validar_evento(db, loja, dados.evento_id)
    if dados.sitcampanha == "ATIVA":
        _desativar_campanhas_mesmo_escopo(
            db, loja_id=loja_id, evento_id=dados.evento_id
        )
    campanha = CampanhaDoacao(
        organizacao_id=loja.organizacao_id,
        loja_id=loja_id,
        **dados.model_dump(),
    )
    db.add(campanha)
    db.commit()
    db.refresh(campanha)
    return _saida(campanha)


@router.put("/{campanha_id}")
def alterar(
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
    if dados.sitcampanha == "ATIVA":
        _desativar_campanhas_mesmo_escopo(
            db,
            loja_id=int(loja.loja_id),
            evento_id=dados.evento_id,
            exceto_id=campanha_id,
        )
    for campo, valor in dados.model_dump().items():
        setattr(campanha, campo, valor)
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
