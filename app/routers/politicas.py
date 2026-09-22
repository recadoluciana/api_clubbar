from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.security import get_operador_logado
from app.database import get_db
from app.models.politicacompra import PoliticaCompra


router = APIRouter(prefix="/politicas", tags=["Políticas Clubbar"])


class PoliticaCompraIn(BaseModel):
    versao: str = Field(min_length=1, max_length=30)
    titulo: str = Field(min_length=3, max_length=160)
    conteudo: str = Field(min_length=20)


def _out(item: PoliticaCompra) -> dict:
    return {
        "politicacompra_id": item.politicacompra_id,
        "versao": item.versao,
        "titulo": item.titulo,
        "conteudo": item.conteudo,
        "sitpolitica": item.sitpolitica,
        "dtiniciovigencia": item.dtiniciovigencia,
        "dtfimvigencia": item.dtfimvigencia,
        "dtcriacao": item.dtcriacao,
    }


@router.get("/compra/vigente")
def consultar_politica_compra_vigente(db: Session = Depends(get_db)):
    item = (
        db.query(PoliticaCompra)
        .filter(PoliticaCompra.sitpolitica == "VIGENTE")
        .order_by(PoliticaCompra.politicacompra_id.desc())
        .first()
    )
    if not item:
        raise HTTPException(404, "Nenhuma política de compra vigente foi publicada.")
    return _out(item)


@router.get("/compra")
def listar_politicas_compra(
    _: dict = Depends(get_operador_logado), db: Session = Depends(get_db)
):
    return [
        _out(item)
        for item in db.query(PoliticaCompra)
        .order_by(PoliticaCompra.politicacompra_id.desc())
        .all()
    ]


@router.post("/compra", status_code=status.HTTP_201_CREATED)
def publicar_politica_compra(
    dados: PoliticaCompraIn,
    operador: dict = Depends(get_operador_logado),
    db: Session = Depends(get_db),
):
    versao = dados.versao.strip()
    if db.query(PoliticaCompra).filter(PoliticaCompra.versao == versao).first():
        raise HTTPException(409, "Já existe uma política com esta versão.")

    agora = datetime.now()
    vigentes = (
        db.query(PoliticaCompra)
        .filter(PoliticaCompra.sitpolitica == "VIGENTE")
        .with_for_update()
        .all()
    )
    for vigente in vigentes:
        vigente.sitpolitica = "ENCERRADA"
        vigente.dtfimvigencia = agora

    item = PoliticaCompra(
        versao=versao,
        titulo=dados.titulo.strip(),
        conteudo=dados.conteudo.strip(),
        sitpolitica="VIGENTE",
        operador_id=int(operador.get("sub") or 0) or None,
        dtiniciovigencia=agora,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _out(item)
