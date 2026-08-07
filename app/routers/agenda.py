from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from app.core.security import get_usuario_logado
from app.database import get_db
from app.models.evento import Evento
from app.models.eventoatracao import EventoAtracao

router=APIRouter(prefix="/agenda-mensal",tags=["Agenda mensal"])

@router.get("")
def listar(loja_id:int,ano:int=Query(ge=2000,le=2200),mes:int=Query(ge=1,le=12),payload=Depends(get_usuario_logado),db:Session=Depends(get_db)):
    try: org=int(payload["organizacao_id"])
    except (KeyError,TypeError,ValueError): raise HTTPException(403,"Organização não identificada no login.")
    inicio=datetime(ano,mes,1); fim=datetime(ano+(mes==12),1 if mes==12 else mes+1,1)
    eventos=(db.query(Evento).outerjoin(EventoAtracao,EventoAtracao.evento_id==Evento.evento_id).filter(
        Evento.organizacao_id==org, Evento.loja_id==loja_id,
        or_(
            (Evento.dtinicioevento<fim) & or_(Evento.dtfimevento>=inicio,Evento.dtinicioevento>=inicio),
            (EventoAtracao.dtinicioatracao>=inicio) & (EventoAtracao.dtinicioatracao<fim),
        ),
    ).distinct().order_by(Evento.dtinicioevento).all())
    saida=[]
    for e in eventos:
        ps=db.query(EventoAtracao).options(joinedload(EventoAtracao.atracao)).filter(EventoAtracao.evento_id==e.evento_id).order_by(EventoAtracao.dtinicioatracao).all()
        saida.append({"evento_id":e.evento_id,"organizacao_id":e.organizacao_id,"loja_id":e.loja_id,"nmtituloevento":e.nmtituloevento,"dtinicioevento":e.dtinicioevento,"dtfimevento":e.dtfimevento,"statusevento":e.statusevento,"urlbannerevento":e.urlbannerevento,"atracoes":[{"eventoatracao_id":p.eventoatracao_id,"atracao_id":p.atracao_id,"dtinicioatracao":p.dtinicioatracao,"dtfimatracao":p.dtfimatracao,"atracao":{"atracao_id":p.atracao.atracao_id,"organizacao_id":p.atracao.organizacao_id,"nmatracao":p.atracao.nmatracao,"dsestilomusical":p.atracao.dsestilomusical,"urlbanneratracao":p.atracao.urlbanneratracao,"dsatracao":p.atracao.dsatracao}} for p in ps]})
    return saida
