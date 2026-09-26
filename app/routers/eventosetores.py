from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.permissoes_loja import validar_mutacao_loja
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.evento import Evento
from app.models.eventolote import EventoLote
from app.models.eventosetor import EventoSetor
from app.models.reserva_ingresso import ReservaIngresso

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


def _validar_teto_capacidade_evento(
    db: Session,
    evento: Evento,
    capacidade_setor: int,
    situacao_setor: str,
    setor_id_atual: int | None = None,
) -> None:
    """Impede que a soma dos setores ultrapasse a lotação da ocorrência."""
    if evento.qtcapacidadeevento is None:
        return
    outros_setores = db.query(func.coalesce(func.sum(EventoSetor.qtcapacidade), 0)).filter(
        EventoSetor.evento_id == evento.evento_id,
        EventoSetor.sitsetor == "ATIVO",
    )
    if setor_id_atual is not None:
        outros_setores = outros_setores.filter(EventoSetor.eventosetor_id != setor_id_atual)
    total = int(outros_setores.scalar() or 0)
    if situacao_setor.upper() == "ATIVO":
        total += capacidade_setor
    if total > int(evento.qtcapacidadeevento):
        raise HTTPException(
            422,
            "A soma das capacidades dos setores não pode ultrapassar a capacidade "
            f"total do evento ({evento.qtcapacidadeevento} pessoas).",
        )

def _atualizar_nomes_lotes_padrao(lotes, nome_anterior: str, nome_novo: str):
    """Mantém o nome automático do lote sincronizado com o setor.

    Só nomes no formato automático "Lote N - ..." são sincronizados.
    """
    for lote in lotes:
        nome_padrao_anterior = f"Lote {lote.nrlote} - {nome_anterior}"
        prefixo_padrao = f"Lote {lote.nrlote} - "
        nome_lote = (lote.nmlote or "").strip()
        if nome_lote == nome_padrao_anterior or nome_lote.startswith(prefixo_padrao):
            lote.nmlote = f"Lote {lote.nrlote} - {nome_novo}"

@router.get("/{evento_id}/setores")
def listar(evento_id:int,db:Session=Depends(get_db),usuario=Depends(get_usuario_logado)):
    _evento(db,evento_id,usuario)
    return [_item(x) for x in db.query(EventoSetor).filter(EventoSetor.evento_id==evento_id).order_by(EventoSetor.nrordem,EventoSetor.nmsetor).all()]

@router.post("/{evento_id}/setores",status_code=201)
def criar(evento_id:int,dados:SetorIn,db:Session=Depends(get_db),usuario=Depends(get_usuario_logado)):
    evento=_evento(db,evento_id,usuario)
    if db.query(EventoSetor).filter(EventoSetor.evento_id==evento_id,EventoSetor.nmsetor==dados.nmsetor.strip()).first(): raise HTTPException(409,"Já existe um setor com esse nome")
    _validar_teto_capacidade_evento(db, evento, dados.qtcapacidade, dados.sitsetor)
    x=EventoSetor(organizacao_id=evento.organizacao_id,loja_id=evento.loja_id,evento_id=evento_id,**dados.model_dump())
    db.add(x);db.commit();db.refresh(x);return _item(x)

@router.put("/setores/{setor_id}")
def editar(setor_id:int,dados:SetorIn,db:Session=Depends(get_db),usuario=Depends(get_usuario_logado)):
    x=db.query(EventoSetor).filter(EventoSetor.eventosetor_id==setor_id).first()
    if not x: raise HTTPException(404,"Setor não encontrado")
    evento = _evento(db,x.evento_id,usuario)
    lotes = db.query(EventoLote).filter(EventoLote.eventosetor_id == setor_id).all()
    nome_anterior = x.nmsetor.strip()
    nome_novo = dados.nmsetor.strip()
    capacidade_comercial = sum(int(lote.qttotallote or 0) for lote in lotes if lote.usarcapacidaderestante != "S")
    vendidos = sum(int(lote.qtvendidalote or 0) for lote in lotes)
    reservados = int(
        db.query(func.coalesce(func.sum(ReservaIngresso.qtreservada), 0)).filter(
            ReservaIngresso.lote_id.in_([lote.lote_id for lote in lotes]),
            ReservaIngresso.sitreserva.in_(("PREENCHENDO", "AGUARDANDO_PAGAMENTO")),
        ).scalar()
        if lotes else 0
    )
    minimo_seguro = max(capacidade_comercial, vendidos + reservados)
    if dados.qtcapacidade < minimo_seguro:
        raise HTTPException(422, f"A capacidade não pode ser menor que {minimo_seguro}, pois há lotes, vendas ou reservas neste setor")
    _validar_teto_capacidade_evento(
        db, evento, dados.qtcapacidade, dados.sitsetor, x.eventosetor_id
    )
    for k,v in dados.model_dump().items():setattr(x,k,v)
    _atualizar_nomes_lotes_padrao(lotes, nome_anterior, nome_novo)
    db.commit();db.refresh(x);return _item(x)

@router.delete("/setores/{setor_id}",status_code=204)
def excluir(setor_id:int,db:Session=Depends(get_db),usuario=Depends(get_usuario_logado)):
    x=db.query(EventoSetor).filter(EventoSetor.eventosetor_id==setor_id).first()
    if not x: raise HTTPException(404,"Setor não encontrado")
    _evento(db,x.evento_id,usuario)
    if db.query(EventoLote).filter(EventoLote.eventosetor_id==setor_id).first():raise HTTPException(409,"O setor possui ingressos cadastrados")
    db.delete(x);db.commit()
