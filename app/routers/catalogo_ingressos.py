from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.models.beneficioingresso import BeneficioIngresso
from app.models.eventolotepreco import EventoLotePreco
from app.models.modalidadebeneficio import ModalidadeBeneficio
from app.models.modalidadeingresso import ModalidadeIngresso


router = APIRouter(prefix="/ingressos-catalogo", tags=["Catálogo de ingressos"])


class ModalidadeIn(BaseModel):
    cdmodalidade: str = Field(min_length=2, max_length=40)
    nmmodalidade: str = Field(min_length=2, max_length=100)
    organizacao_id: int | None = None
    tipomodalidade: str = Field(pattern="^(PADRAO|LEGAL|COMERCIAL)$")
    aplicacotalegal: bool = False
    exigebeneficio: bool = False
    exigecomprovante: bool = False
    permitepersonalizarnome: bool = True
    situacao: str = Field(default="ATIVO", pattern="^(ATIVO|INATIVO)$")
    nrordem: int = Field(default=1, ge=1)
    beneficios_ids: list[int] = Field(default_factory=list)


class BeneficioIn(BaseModel):
    cdbeneficio: str = Field(min_length=2, max_length=40)
    nmbeneficio: str = Field(min_length=2, max_length=100)
    exigecomprovante: bool = True
    situacao: str = Field(default="ATIVO", pattern="^(ATIVO|INATIVO)$")
    nrordem: int = Field(default=1, ge=1)
    dtiniciovigencia: datetime | None = None
    dtfimvigencia: datetime | None = None


def _beneficio_out(item: BeneficioIngresso) -> dict:
    return {
        "beneficio_id": item.beneficio_id,
        "cdbeneficio": item.cdbeneficio,
        "nmbeneficio": item.nmbeneficio,
        "exigecomprovante": bool(item.exigecomprovante),
        "situacao": item.situacao,
        "nrordem": int(item.nrordem),
        "dtiniciovigencia": item.dtiniciovigencia,
        "dtfimvigencia": item.dtfimvigencia,
    }


def _modalidade_out(db: Session, item: ModalidadeIngresso) -> dict:
    beneficios = (
        db.query(BeneficioIngresso)
        .join(ModalidadeBeneficio, ModalidadeBeneficio.beneficio_id == BeneficioIngresso.beneficio_id)
        .filter(ModalidadeBeneficio.modalidade_id == item.modalidade_id)
        .order_by(BeneficioIngresso.nrordem, BeneficioIngresso.nmbeneficio)
        .all()
    )
    return {
        "modalidade_id": item.modalidade_id,
        "organizacao_id": item.organizacao_id,
        "cdmodalidade": item.cdmodalidade,
        "nmmodalidade": item.nmmodalidade,
        "tipomodalidade": item.tipomodalidade,
        "aplicacotalegal": bool(item.aplicacotalegal),
        "exigebeneficio": bool(item.exigebeneficio),
        "exigecomprovante": bool(item.exigecomprovante),
        "permitepersonalizarnome": bool(item.permitepersonalizarnome),
        "situacao": item.situacao,
        "nrordem": int(item.nrordem),
        "beneficios": [_beneficio_out(i) for i in beneficios],
    }


def _sincronizar_beneficios(db: Session, modalidade: ModalidadeIngresso, ids: list[int]) -> None:
    ids_unicos = sorted(set(ids)) if modalidade.exigebeneficio else []
    if ids_unicos:
        encontrados = db.query(BeneficioIngresso.beneficio_id).filter(BeneficioIngresso.beneficio_id.in_(ids_unicos)).all()
        if len(encontrados) != len(ids_unicos):
            raise HTTPException(422, "Há benefícios inexistentes na seleção")
    db.query(ModalidadeBeneficio).filter(ModalidadeBeneficio.modalidade_id == modalidade.modalidade_id).delete()
    db.add_all(ModalidadeBeneficio(modalidade_id=modalidade.modalidade_id, beneficio_id=i) for i in ids_unicos)


@router.get("/beneficios")
def listar_beneficios(incluir_inativos: bool = False, db: Session = Depends(get_db)):
    query = db.query(BeneficioIngresso)
    if not incluir_inativos:
        query = query.filter(BeneficioIngresso.situacao == "ATIVO")
    return [_beneficio_out(i) for i in query.order_by(BeneficioIngresso.nrordem, BeneficioIngresso.nmbeneficio).all()]


@router.get("/modalidades")
def listar_modalidades(organizacao_id: int | None = None, incluir_inativos: bool = False, db: Session = Depends(get_db)):
    query = db.query(ModalidadeIngresso)
    if organizacao_id is None:
        query = query.filter(ModalidadeIngresso.organizacao_id.is_(None))
    else:
        query = query.filter(or_(ModalidadeIngresso.organizacao_id.is_(None), ModalidadeIngresso.organizacao_id == organizacao_id))
    if not incluir_inativos:
        query = query.filter(ModalidadeIngresso.situacao == "ATIVO")
    return [_modalidade_out(db, i) for i in query.order_by(ModalidadeIngresso.nrordem, ModalidadeIngresso.nmmodalidade).all()]


@router.post("/beneficios", status_code=status.HTTP_201_CREATED)
def criar_beneficio(dados: BeneficioIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    codigo = dados.cdbeneficio.strip().upper()
    if db.query(BeneficioIngresso).filter(BeneficioIngresso.cdbeneficio == codigo).first():
        raise HTTPException(409, "Já existe um benefício com este código")
    item = BeneficioIngresso(**dados.model_dump(exclude={"cdbeneficio"}), cdbeneficio=codigo)
    db.add(item); db.commit(); db.refresh(item)
    return _beneficio_out(item)


@router.put("/beneficios/{beneficio_id}")
def alterar_beneficio(beneficio_id: int, dados: BeneficioIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(BeneficioIngresso).filter(BeneficioIngresso.beneficio_id == beneficio_id).first()
    if not item: raise HTTPException(404, "Benefício não encontrado")
    codigo = dados.cdbeneficio.strip().upper()
    duplicado = db.query(BeneficioIngresso).filter(BeneficioIngresso.cdbeneficio == codigo, BeneficioIngresso.beneficio_id != beneficio_id).first()
    if duplicado: raise HTTPException(409, "Já existe um benefício com este código")
    for campo, valor in dados.model_dump().items(): setattr(item, campo, codigo if campo == "cdbeneficio" else valor)
    db.commit(); db.refresh(item)
    return _beneficio_out(item)


@router.post("/modalidades", status_code=status.HTTP_201_CREATED)
def criar_modalidade(dados: ModalidadeIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    codigo = dados.cdmodalidade.strip().upper()
    if db.query(ModalidadeIngresso).filter(ModalidadeIngresso.cdmodalidade == codigo).first():
        raise HTTPException(409, "Já existe uma modalidade com este código")
    item = ModalidadeIngresso(**dados.model_dump(exclude={"cdmodalidade", "beneficios_ids"}), cdmodalidade=codigo)
    db.add(item); db.flush(); _sincronizar_beneficios(db, item, dados.beneficios_ids)
    db.commit(); db.refresh(item)
    return _modalidade_out(db, item)


@router.put("/modalidades/{modalidade_id}")
def alterar_modalidade(modalidade_id: int, dados: ModalidadeIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(ModalidadeIngresso).filter(ModalidadeIngresso.modalidade_id == modalidade_id).first()
    if not item: raise HTTPException(404, "Modalidade não encontrada")
    codigo = dados.cdmodalidade.strip().upper()
    duplicado = db.query(ModalidadeIngresso).filter(ModalidadeIngresso.cdmodalidade == codigo, ModalidadeIngresso.modalidade_id != modalidade_id).first()
    if duplicado: raise HTTPException(409, "Já existe uma modalidade com este código")
    for campo, valor in dados.model_dump(exclude={"beneficios_ids"}).items(): setattr(item, campo, codigo if campo == "cdmodalidade" else valor)
    _sincronizar_beneficios(db, item, dados.beneficios_ids)
    db.commit(); db.refresh(item)
    return _modalidade_out(db, item)


@router.delete("/modalidades/{modalidade_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_modalidade(modalidade_id: int, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(ModalidadeIngresso).filter(ModalidadeIngresso.modalidade_id == modalidade_id).first()
    if not item: raise HTTPException(404, "Modalidade não encontrada")
    if db.query(EventoLotePreco.lotepreco_id).filter(EventoLotePreco.modalidade_id == modalidade_id).first():
        raise HTTPException(409, "Esta modalidade já foi utilizada. Inative-a em vez de excluir.")
    db.delete(item); db.commit()


@router.delete("/beneficios/{beneficio_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_beneficio(beneficio_id: int, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(BeneficioIngresso).filter(BeneficioIngresso.beneficio_id == beneficio_id).first()
    if not item: raise HTTPException(404, "Benefício não encontrado")
    if db.query(ModalidadeBeneficio).filter(ModalidadeBeneficio.beneficio_id == beneficio_id).first():
        raise HTTPException(409, "Este benefício está vinculado a uma modalidade. Remova o vínculo ou inative-o.")
    db.delete(item); db.commit()
