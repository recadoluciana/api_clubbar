from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.models.taxapadrao import TaxaPadrao
from app.services.taxa_service import taxa_padrao_vigente


router = APIRouter(prefix="/taxas-padrao", tags=["Taxas padrão"])


class TaxaPadraoIn(BaseModel):
    pctaxaproduto: Decimal = Field(ge=0, le=100)
    pctaxaingresso: Decimal = Field(ge=0, le=100)
    vrtaxaminimaingresso: Decimal = Field(ge=0)


def _out(item: TaxaPadrao) -> dict:
    return {
        "taxapadrao_id": item.taxapadrao_id, "nrversao": item.nrversao,
        "pctaxaproduto": float(item.pctaxaproduto), "pctaxaingresso": float(item.pctaxaingresso),
        "vrtaxaminimaingresso": float(item.vrtaxaminimaingresso),
        "sittaxapadrao": item.sittaxapadrao, "dtiniciovigencia": item.dtiniciovigencia,
        "dtfimvigencia": item.dtfimvigencia, "dtcriacao": item.dtcriacao,
    }


@router.get("/vigente")
def consultar_vigente(db: Session = Depends(get_db)):
    return _out(taxa_padrao_vigente(db))


@router.get("")
def listar(_: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    return [_out(i) for i in db.query(TaxaPadrao).order_by(TaxaPadrao.nrversao.desc()).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def criar(dados: TaxaPadraoIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    ultima = db.query(TaxaPadrao).order_by(TaxaPadrao.nrversao.desc()).first()
    item = TaxaPadrao(nrversao=(ultima.nrversao + 1 if ultima else 1), **dados.model_dump(), sittaxapadrao="RASCUNHO")
    db.add(item); db.commit(); db.refresh(item)
    return _out(item)


@router.put("/{taxapadrao_id}")
def alterar(taxapadrao_id: int, dados: TaxaPadraoIn, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(TaxaPadrao).filter(TaxaPadrao.taxapadrao_id == taxapadrao_id).first()
    if not item: raise HTTPException(404, "Versão de taxas não encontrada")
    if item.sittaxapadrao != "RASCUNHO": raise HTTPException(409, "Somente uma versão em rascunho pode ser alterada")
    for campo, valor in dados.model_dump().items(): setattr(item, campo, valor)
    db.commit(); db.refresh(item)
    return _out(item)


@router.post("/{taxapadrao_id}/vigorar")
def vigorar(taxapadrao_id: int, _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)):
    item = db.query(TaxaPadrao).filter(TaxaPadrao.taxapadrao_id == taxapadrao_id).with_for_update().first()
    if not item: raise HTTPException(404, "Versão de taxas não encontrada")
    if item.sittaxapadrao != "RASCUNHO": raise HTTPException(409, "Somente um rascunho pode entrar em vigor")
    agora = datetime.now()
    vigentes = db.query(TaxaPadrao).filter(TaxaPadrao.sittaxapadrao == "VIGENTE").with_for_update().all()
    for vigente in vigentes:
        vigente.sittaxapadrao = "ENCERRADA"; vigente.dtfimvigencia = agora
    item.sittaxapadrao = "VIGENTE"; item.dtiniciovigencia = agora
    db.commit(); db.refresh(item)
    return _out(item)
