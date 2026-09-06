from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.models.contratopadrao import ContratoPadrao


router = APIRouter(prefix="/contratos-padrao", tags=["Contratos padrão"])


class ContratoPadraoCreate(BaseModel):
    versao: str = Field(min_length=1, max_length=30)
    titulo: str = Field(min_length=3, max_length=160)
    conteudomodelo: str = Field(min_length=100)
    vrimplantacao: Decimal = Field(default=Decimal("0"), ge=0)


def _out(item: ContratoPadrao) -> dict:
    return {
        "contratopadrao_id": item.contratopadrao_id,
        "versao": item.versao,
        "titulo": item.titulo,
        "conteudomodelo": item.conteudomodelo,
        "vrimplantacao": float(item.vrimplantacao),
        "sitcontrato": item.sitcontrato,
        "operador_id": item.operador_id,
        "dtvigencia": item.dtvigencia,
        "dtcriacao": item.dtcriacao,
    }


@router.get("")
def listar(_: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    return [_out(item) for item in db.query(ContratoPadrao).order_by(
        ContratoPadrao.contratopadrao_id.desc()
    ).all()]


@router.get("/ativo")
def consultar_ativo(_: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(ContratoPadrao).filter(
        ContratoPadrao.sitcontrato == "ATIVO"
    ).order_by(ContratoPadrao.contratopadrao_id.desc()).first()
    if not item:
        raise HTTPException(404, "Nenhum contrato padrão ativo")
    return _out(item)


@router.post("", status_code=status.HTTP_201_CREATED)
def publicar_nova_versao(
    dados: ContratoPadraoCreate,
    operador: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    versao = dados.versao.strip()
    if db.query(ContratoPadrao).filter(ContratoPadrao.versao == versao).first():
        raise HTTPException(409, "Já existe um contrato com esta versão")
    db.query(ContratoPadrao).filter(
        ContratoPadrao.sitcontrato == "ATIVO"
    ).with_for_update().all()
    db.query(ContratoPadrao).filter(ContratoPadrao.sitcontrato == "ATIVO").update(
        {ContratoPadrao.sitcontrato: "INATIVO"}, synchronize_session=False
    )
    item = ContratoPadrao(
        versao=versao,
        titulo=dados.titulo.strip(),
        conteudomodelo=dados.conteudomodelo.strip(),
        vrimplantacao=dados.vrimplantacao,
        sitcontrato="ATIVO",
        operador_id=int(operador.get("sub") or 0) or None,
        dtvigencia=datetime.now(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _out(item)
