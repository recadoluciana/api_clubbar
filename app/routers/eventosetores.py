from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventosetor import EventoSetor

router = APIRouter(prefix="/eventos", tags=["Setores de eventos"])

class SetorIn(BaseModel):
    nmsetor: str = Field(min_length=1, max_length=100)
    dssetor: str | None = Field(default=None, max_length=255)
    qtcapacidade: int = Field(gt=0)
    nrordem: int = Field(default=1, gt=0)
    sitsetor: str = "ATIVO"

def _evento(db, evento_id, usuario):
    evento=db.query(Evento).filter(Evento.evento_id==evento_id).first()
    if not evento: raise HTTPException(404,"Evento não encontrado")
    validar_mutacao_loja(usuario,evento.organizacao_id,evento.loja_id)
    return evento

def _item(x):
    return {"eventosetor_id":x.eventosetor_id,"organizacao_id":x.organizacao_id,"loja_id":x.loja_id,"evento_id":x.evento_id,"nmsetor":x.nmsetor,"dssetor":x.dssetor,"qtcapacidade":x.qtcapacidade,"nrordem":x.nrordem,"sitsetor":x.sitsetor}

@router.get("/{evento_id}/setores")
def listar(evento_id:int,db:Session=Depends(get_db),usuario=Depends(get_usuario_logado)):
    _evento(db,evento_id,usuario)
    return [_item(x) for x in db.query(EventoSetor).filter(EventoSetor.evento_id==evento_id).order_by(EventoSetor.nrordem,EventoSetor.nmsetor).all()]

@router.post("/{evento_id}/setores",status_code=201)
def criar(evento_id:int,dados:SetorIn,db:Session=Depends(get_db),usuario=Depends(get_usuario_logado)):
    evento=_evento(db,evento_id,usuario)
    if db.query(EventoSetor).filter(EventoSetor.evento_id==evento_id,EventoSetor.nmsetor==dados.nmsetor.strip()).first(): raise HTTPException(409,"Já existe um setor com esse nome")
    x=EventoSetor(organizacao_id=evento.organizacao_id,loja_id=evento.loja_id,evento_id=evento_id,**dados.model_dump())
    db.add(x);db.commit();db.refresh(x);return _item(x)

@router.put("/setores/{setor_id}")
def editar(setor_id:int,dados:SetorIn,db:Session=Depends(get_db),usuario=Depends(get_usuario_logado)):
    x=db.query(EventoSetor).filter(EventoSetor.eventosetor_id==setor_id).first()
    if not x: raise HTTPException(404,"Setor não encontrado")
    _evento(db,x.evento_id,usuario)
    for k,v in dados.model_dump().items():setattr(x,k,v)
    db.commit();db.refresh(x);return _item(x)

@router.delete("/setores/{setor_id}",status_code=204)
def excluir(setor_id:int,db:Session=Depends(get_db),usuario=Depends(get_usuario_logado)):
    x=db.query(EventoSetor).filter(EventoSetor.eventosetor_id==setor_id).first()
    if not x: raise HTTPException(404,"Setor não encontrado")
    _evento(db,x.evento_id,usuario)
    if db.query(EventoLote).filter(EventoLote.eventosetor_id==setor_id).first():raise HTTPException(409,"O setor possui ingressos cadastrados")
    db.delete(x);db.commit()
